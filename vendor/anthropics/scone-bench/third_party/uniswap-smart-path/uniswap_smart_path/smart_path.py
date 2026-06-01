import asyncio
import logging
from collections.abc import Awaitable, Sequence
from typing import (
    Any,
    cast,
)

from web3 import (
    AsyncHTTPProvider,
    AsyncWeb3,
)
from web3.contract import AsyncContract
from web3.contract.async_contract import AsyncContractFunctions
from web3.exceptions import BadFunctionCallOutput
from web3.middleware import validation
from web3.types import (
    ChecksumAddress,
    RPCEndpoint,
    Wei,
)

from ._constants import (
    erc20_abi,
    pancakeswapv3_pool_abi,
    pivot_tokens,
    uniswapv2_abi,
    uniswapv2_address,
    uniswapv2_factory_abi,
    uniswapv2_factory_address,
    uniswapv2_pair_abi,
    uniswapv3_factory_abi,
    uniswapv3_factory_address,
    uniswapv3_pool_abi,
    uniswapv3_quoter_address,
    uniswapv3_quoterv1_abi,
    v3_pool_fees,
)
from ._datastructures import (
    CandidateV2Pool,
    CandidateV3Pool,
    RouterFunction,
    Token,
    V2OrderedPool,
    V2PoolPath,
    V3OrderedPool,
    V3PoolPath,
    WeightedPath,
    WeightedPathResult,
)
from ._utilities import is_null_address
from .exceptions import SmartPathException
from .smart_rate_limiter import (
    SmartRateLimiter,
    _rate_limit,
)

logger = logging.getLogger(__name__)


NO_VALIDATION_METHODS = [RPCEndpoint("eth_call")]  # to avoid unnecessary eth_chainId requests


class SmartPath:
    def __init__(
        self,
        w3: AsyncWeb3,
        with_gas_estimate: bool = False,
        chain_id: int = 1,
        with_v2: bool = True,
        with_v3: bool = True,
        smart_rate_limiter: SmartRateLimiter | None = None,
        **kwargs: Any,
    ) -> None:
        if with_gas_estimate:
            raise NotImplementedError("Gas is not yet estimated")
        self.w3 = w3
        for method in NO_VALIDATION_METHODS:
            if method in validation.METHODS_TO_VALIDATE:
                logger.debug(f"Removing {method} from web3.middleware.validation.METHODS_TO_VALIDATE")
                validation.METHODS_TO_VALIDATE.remove(method)
        self.chain_id = chain_id
        self.with_v2 = with_v2
        self.with_v3 = with_v3

        self.pivots = kwargs.get("pivot_tokens") or pivot_tokens[self.chain_id]

        if self.with_v2:
            v2_router = w3.to_checksum_address(kwargs.get("v2_router") or uniswapv2_address)
            self.uniswapv2 = self.w3.eth.contract(v2_router, abi=uniswapv2_abi)
            V2PoolPath.contract = self.uniswapv2

            v2_factory = w3.to_checksum_address(kwargs.get("v2_factory") or uniswapv2_factory_address)
            self.factoryv2 = self.w3.eth.contract(v2_factory, abi=uniswapv2_factory_abi)

        if self.with_v3:
            self.v3_pool_fees = tuple(kwargs.get("v3_pool_fees") or v3_pool_fees)

            v3_quoter = w3.to_checksum_address(kwargs.get("v3_quoter") or uniswapv3_quoter_address)

            # Assume that quoter is V1. TODO: Detect V1 vs V2 dynamically
            self.quoter = self.w3.eth.contract(v3_quoter, abi=uniswapv3_quoterv1_abi)
            V3PoolPath.contract = self.quoter

            # # Auto-detect quoter version by checking contract bytecode or attempting a call
            # # First try with V2 ABI (has 4 return values)
            # try:
            #     self.quoter = self.w3.eth.contract(v3_quoter, abi=uniswapv3_quoter_abi)
            #     # Try to access the function - if it exists with V2 signature, we're good
            #     # Note: We can't actually call it here without valid input, but we set up for later detection
            #     V3PoolPath.contract = self.quoter
            #     logger.debug(f"Initialized V3 quoter at {v3_quoter} - version will be detected on first use")
            # except Exception as e:
            #     # If there's an issue, try V1
            #     logger.debug(f"Could not initialize quoter as V2, trying V1: {e}")
            #     self.quoter = self.w3.eth.contract(v3_quoter, abi=uniswapv3_quoterv1_abi)
            #     V3PoolPath.contract = self.quoter

            v3_factory = w3.to_checksum_address(kwargs.get("v3_factory") or uniswapv3_factory_address)
            self.factoryv3 = self.w3.eth.contract(v3_factory, abi=uniswapv3_factory_abi)

        self.smart_rate_limiter = smart_rate_limiter

    def get_smart_rate_limiter(self) -> SmartRateLimiter | None:
        return self.smart_rate_limiter

    @classmethod
    async def create(
        cls,
        w3: AsyncWeb3 | None = None,
        rpc_endpoint: str | None = None,
        with_gas_estimate: bool = False,
        smart_rate_limiter: SmartRateLimiter | None = None,
    ) -> "SmartPath":
        """
        Create a SmartPath instance which will search for the best path from v2 and v3 pools.

        :param w3: a valid AsyncWeb3 instance (if no rpc endpoint is given)
        :param rpc_endpoint: an rpc endpoint address (if no w3 instance is given)
        :param with_gas_estimate: Not supported at the moment.
        :param smart_rate_limiter: an instance of SmartRateLimiter to manage rate limits
        :return: a SmartPath instance using v2 and v3 pools
        """
        _w3 = await cls._get_w3(rpc_endpoint, w3)
        chain_id = await _w3.eth.chain_id
        logger.debug(f"Creating SmartPath for V2 and V3 pools on chain id: {chain_id}")
        return cls(_w3, with_gas_estimate, chain_id, True, True, smart_rate_limiter)

    @classmethod
    async def create_v2_only(
        cls,
        w3: AsyncWeb3 | None = None,
        rpc_endpoint: str | None = None,
        with_gas_estimate: bool = False,
        smart_rate_limiter: SmartRateLimiter | None = None,
    ) -> "SmartPath":
        """
        Create a SmartPath instance which will search for the best path from v2 pools only.

        :param w3: a valid AsyncWeb3 instance (if no rpc endpoint is given)
        :param rpc_endpoint: an rpc endpoint address (if no w3 instance is given)
        :param with_gas_estimate: Not supported at the moment.
        :param smart_rate_limiter: an instance of SmartRateLimiter to manage rate limits
        :return: a SmartPath instance using only v2 pools
        """
        _w3 = await cls._get_w3(rpc_endpoint, w3)
        chain_id = await _w3.eth.chain_id
        logger.debug(f"Creating SmartPath for V2 only pool son chain id: {chain_id}")
        return cls(_w3, with_gas_estimate, chain_id, True, False, smart_rate_limiter)

    @classmethod
    async def create_v3_only(
        cls,
        w3: AsyncWeb3 | None = None,
        rpc_endpoint: str | None = None,
        with_gas_estimate: bool = False,
        smart_rate_limiter: SmartRateLimiter | None = None,
    ) -> "SmartPath":
        """
        Create a SmartPath instance which will search for the best path from v3 pools only.

        :param w3: a valid AsyncWeb3 instance (if no rpc endpoint is given)
        :param rpc_endpoint: an rpc endpoint address (if no w3 instance is given)
        :param with_gas_estimate: Not supported at the moment.
        :param smart_rate_limiter: an instance of SmartRateLimiter to manage rate limits
        :return: a SmartPath instance using only v3 pools
        """
        _w3 = await cls._get_w3(rpc_endpoint, w3)
        chain_id = await _w3.eth.chain_id
        logger.debug(f"Creating SmartPath for V3 only pools on chain id: {chain_id}")
        return cls(_w3, with_gas_estimate, chain_id, False, True, smart_rate_limiter)

    @classmethod
    async def create_custom(
        cls,
        w3: AsyncWeb3 | None = None,
        rpc_endpoint: str | None = None,
        with_gas_estimate: bool = False,
        smart_rate_limiter: SmartRateLimiter | None = None,
        **kwargs: Any,
    ) -> "SmartPath":
        """
        Create a SmartPath instance with custom V2 and/or v3 addresses and pivot tokens. Customization is done thanks
        to the following optional keyword arguments:

        * pivot_tokens: Sequence[str] - addresses of the token used for multi-hop pools, like weth, usdc, usdt, dai, ...
        * v3_pool_fees: tuple of v3 fees as basis point. eg: (100, 500, 3000, 10000)
        * v2_router: str - v2 router address
        * v2_factory: str - v2 factory address
        * v3_quoter: str - v3 quoter address (automatically detects QuoterV1 vs QuoterV2)
        * v3_factory: str - v3 factory address

        :param w3: a valid AsyncWeb3 instance (if no rpc endpoint is given)
        :param rpc_endpoint: an rpc endpoint address (if no w3 instance is given)
        :param with_gas_estimate: Not supported at the moment.
        :param smart_rate_limiter: an instance of SmartRateLimiter to manage rate limits
        :param kwargs: keyword args to customize V2 and/or V3 pools (see above)
        :return: a custom SmartPath instance
        """
        _w3 = await cls._get_w3(rpc_endpoint, w3)
        _chain_id = await _w3.eth.chain_id
        logger.debug(f"Creating custom SmartPath on chain id: {_chain_id}")

        if kwargs.get("pivot_tokens"):
            pivots = tuple(cast(Sequence[str], kwargs.get("pivot_tokens")))
            _pivots = await cls._get_pivot_tokens(pivots, _w3)
        else:
            _pivots = None

        with_v2 = kwargs.get("v2_router") and kwargs.get("v2_factory")
        with_v3 = kwargs.get("v3_quoter") and kwargs.get("v3_factory")
        if not with_v2 and not with_v3:
            raise SmartPathException("Must provide v2 and/or v3 addresses")

        return cls(
            _w3,
            with_gas_estimate,
            _chain_id,
            with_v2=bool(with_v2),
            with_v3=bool(with_v3),
            smart_rate_limiter=smart_rate_limiter,
            pivot_tokens=_pivots,
            v3_pool_fees=kwargs.get("v3_pool_fees"),
            v2_router=kwargs.get("v2_router"),
            v2_factory=kwargs.get("v2_factory"),
            v3_quoter=kwargs.get("v3_quoter"),
            v3_factory=kwargs.get("v3_factory"),
        )

    @staticmethod
    async def _get_pivot_tokens(pivots: Sequence[str], w3: AsyncWeb3) -> tuple[Token, ...]:
        pivot_coros = [
            SmartPath._get_token_at_creation(AsyncWeb3.to_checksum_address(pivot), w3) for pivot in pivots
        ]
        return tuple(await asyncio.gather(*pivot_coros))

    @staticmethod
    async def _get_w3(rpc_endpoint: str | None, w3: AsyncWeb3 | None) -> AsyncWeb3:
        if w3:
            _w3 = w3
        elif rpc_endpoint:
            _w3 = AsyncWeb3(AsyncHTTPProvider(rpc_endpoint, {"timeout": 60}))
        else:
            raise ValueError(
                "Invalid parameters. Must provide either an AsyncWeb3 instance or an rpc address"
            )
        return _w3

    async def _get_symbol(self, contract: AsyncContract) -> str:
        try:
            return str(await self._contract_function_call(contract.functions.symbol()))
        except (BadFunctionCallOutput, OverflowError) as e:
            raise SmartPathException(
                f"Failed to get token symbol from contract {contract.address}: {e}"
            ) from e

    @_rate_limit("eth_call")
    async def _contract_function_call(self, contract_function: AsyncContractFunctions) -> Any:
        return await cast(Awaitable[Any], contract_function.call())

    async def _get_token(self, address: ChecksumAddress, w3: AsyncWeb3) -> Token:
        erc20 = w3.eth.contract(address, abi=erc20_abi)
        symbol, decimals = await asyncio.gather(
            self._get_symbol(erc20), self._contract_function_call(erc20.functions.decimals())
        )
        return Token(AsyncWeb3.to_checksum_address(address), symbol, decimals)

    @staticmethod
    async def _get_token_at_creation(address: ChecksumAddress, w3: AsyncWeb3) -> Token:
        erc20 = w3.eth.contract(address, abi=erc20_abi)
        symbol, decimals = await asyncio.gather(
            erc20.functions.symbol().call(),
            erc20.functions.decimals().call(),
        )
        return Token(AsyncWeb3.to_checksum_address(address), symbol, decimals)

    async def _get_v2_pool_details(self, from_token: Token, to_token: Token) -> CandidateV2Pool:
        pool_address = await self._contract_function_call(
            self.factoryv2.functions.getPair(from_token.address, to_token.address)
        )

        if not AsyncWeb3.is_checksum_address(pool_address) or is_null_address(pool_address):
            return CandidateV2Pool(from_token, to_token, False)

        pair_contract = self.w3.eth.contract(pool_address, abi=uniswapv2_pair_abi)
        reserves, pair_token0, pair_token1 = await asyncio.gather(
            self._contract_function_call(pair_contract.functions.getReserves()),
            self._contract_function_call(pair_contract.functions.token0()),
            self._contract_function_call(pair_contract.functions.token1()),
        )

        reserve0, reserve1 = reserves[0], reserves[1]

        # Determine token order in the pair and map to from/to
        if pair_token0.lower() == from_token.address.lower():
            from_reserve, to_reserve = Wei(reserve0), Wei(reserve1)
        else:
            from_reserve, to_reserve = Wei(reserve1), Wei(reserve0)

        # Calculate exchange rate (from_token per to_token)
        # This is how many from_tokens you need to get 1 to_token
        decimal_adjusted_to_per_from_exchange_rate = 0.0
        if from_reserve > 0:
            # Adjust for decimals
            adjusted_from_reserve = float(from_reserve) / (10**from_token.decimals)
            adjusted_to_reserve = float(to_reserve) / (10**to_token.decimals)
            decimal_adjusted_to_per_from_exchange_rate = adjusted_to_reserve / adjusted_from_reserve

        return CandidateV2Pool(
            from_token=from_token,
            to_token=to_token,
            exists=True,
            from_reserve=from_reserve,
            to_reserve=to_reserve,
            decimal_adjusted_to_per_from_exchange_rate=decimal_adjusted_to_per_from_exchange_rate,
        )

    async def _get_v3_pool_details(self, from_token: Token, to_token: Token, fees: int) -> CandidateV3Pool:
        pool_address = await self._contract_function_call(
            self.factoryv3.functions.getPool(from_token.address, to_token.address, fees)
        )

        if not AsyncWeb3.is_checksum_address(pool_address) or is_null_address(pool_address):
            return CandidateV3Pool(from_token, to_token, False, fees)

        pool_contract = self.w3.eth.contract(pool_address, abi=uniswapv3_pool_abi)

        # Get pool token addresses and slot0 in parallel
        try:
            pool_token0, pool_token1, slot0 = await asyncio.gather(
                self._contract_function_call(pool_contract.functions.token0()),
                self._contract_function_call(pool_contract.functions.token1()),
                self._contract_function_call(pool_contract.functions.slot0()),
            )
        except Exception:
            # If slot0 fails (likely PancakeSwap pool), retry with PancakeSwap ABI
            pool_contract_pancake = self.w3.eth.contract(pool_address, abi=pancakeswapv3_pool_abi)
            try:
                # We already have token0/token1 or they failed too, so get all three again
                pool_token0, pool_token1, slot0 = await asyncio.gather(
                    self._contract_function_call(pool_contract.functions.token0()),
                    self._contract_function_call(pool_contract.functions.token1()),
                    self._contract_function_call(pool_contract_pancake.functions.slot0()),
                )
            except Exception:
                # If it still fails, return pool as non-existent
                return CandidateV3Pool(from_token, to_token, False, fees)

        # Get token balances
        token0_contract = self.w3.eth.contract(pool_token0, abi=erc20_abi)
        token1_contract = self.w3.eth.contract(pool_token1, abi=erc20_abi)

        balance0, balance1 = await asyncio.gather(
            self._contract_function_call(token0_contract.functions.balanceOf(pool_address)),
            self._contract_function_call(token1_contract.functions.balanceOf(pool_address)),
        )

        sqrtPriceX96 = slot0[0]

        # Determine token order and map balances to from/to
        if pool_token0.lower() == from_token.address.lower():
            is_from_first = True
            from_balance = Wei(balance0)
            to_balance = Wei(balance1)
        else:
            is_from_first = False
            from_balance = Wei(balance1)
            to_balance = Wei(balance0)

        # Calculate price from sqrtPriceX96
        # sqrtPriceX96 = sqrt(price) * 2^96
        # price = (sqrtPriceX96 / 2^96)^2
        price_raw = (float(sqrtPriceX96) / (2**96)) ** 2

        # Calculate exchange rate (from_token per to_token) with proper decimal adjustment
        if is_from_first:
            # Price is already in the right direction
            decimal_adjusted_to_per_from_exchange_rate = price_raw * (
                10 ** (to_token.decimals - from_token.decimals)
            )
        else:
            # Price is token0/token1, so we need to invert for from/to rate
            decimal_adjusted_to_per_from_exchange_rate = (
                (1 / price_raw) * (10 ** (to_token.decimals - from_token.decimals)) if price_raw > 0 else 0.0
            )

        return CandidateV3Pool(
            from_token=from_token,
            to_token=to_token,
            exists=True,
            fee=fees,
            from_balance=from_balance,
            to_balance=to_balance,
            decimal_adjusted_to_per_from_exchange_rate=decimal_adjusted_to_per_from_exchange_rate,
        )

    async def _build_v2_path_list(
        self, token_in: Token, token_out: Token
    ) -> tuple[list[V2PoolPath], list[CandidateV2Pool]]:
        v2_path_list: list[V2PoolPath] = []

        if not self.with_v2:
            return v2_path_list, []

        filtered_pivots = [pivot for pivot in self.pivots if pivot not in (token_in, token_out)]

        # Collect all candidate pools
        direct_pool_coro = self._get_v2_pool_details(token_in, token_out)

        # Pools with from = token_in (sorted by to_token for consistency)
        token_in_pools_coros = [
            self._get_v2_pool_details(token_in, pivot)
            for pivot in sorted(filtered_pivots, key=lambda t: t.address)
        ]

        # Pools with to = token_out (sorted by from_token for consistency)
        token_out_pools_coros = [
            self._get_v2_pool_details(pivot, token_out)
            for pivot in sorted(filtered_pivots, key=lambda t: t.address)
        ]

        # Execute all pool queries
        all_pool_coros = [direct_pool_coro] + token_in_pools_coros + token_out_pools_coros
        candidate_pools = await asyncio.gather(*all_pool_coros)

        # Build paths from existing pools
        direct_pool = candidate_pools[0]
        if direct_pool.exists:
            v2_path_list.append(V2PoolPath((V2OrderedPool(token_in, token_out),), self.smart_rate_limiter))

        # Check pivot paths - need to find matching in/out pairs
        token_in_pools = candidate_pools[1 : 1 + len(filtered_pivots)]  # pools with from = token_in
        token_out_pools = candidate_pools[1 + len(filtered_pivots) :]  # pools with to = token_out

        # For each pivot, check if we have both in and out pools
        sorted_pivots = sorted(filtered_pivots, key=lambda t: t.address)
        for i, pivot_token in enumerate(sorted_pivots):
            token_in_pool = token_in_pools[i]  # token_in -> pivot
            token_out_pool = token_out_pools[i]  # pivot -> token_out

            if token_in_pool.exists and token_out_pool.exists:
                v2_path_list.append(
                    V2PoolPath(
                        (V2OrderedPool(token_in, pivot_token), V2OrderedPool(pivot_token, token_out)),
                        self.smart_rate_limiter,
                    )
                )

        return v2_path_list, candidate_pools

    async def _build_v3_path_list(
        self, token_in: Token, token_out: Token
    ) -> tuple[list[V3PoolPath], list[CandidateV3Pool]]:
        v3_path_list: list[V3PoolPath] = []

        if not self.with_v3:
            return v3_path_list, []

        filtered_pivots = [pivot for pivot in self.pivots if pivot not in (token_in, token_out)]
        sorted_pivots = sorted(filtered_pivots, key=lambda t: t.address)

        # Collect candidate pools in specified order:
        # 1. Direct token_in -> token_out pools (sorted by fee)
        direct_pool_coros = [
            self._get_v3_pool_details(token_in, token_out, fees) for fees in sorted(self.v3_pool_fees)
        ]

        # 2. Pools with from = token_in, sorted by to_token then by fee
        token_in_pools_coros = []
        for pivot in sorted_pivots:
            for fees in sorted(self.v3_pool_fees):
                token_in_pools_coros.append(self._get_v3_pool_details(token_in, pivot, fees))

        # 3. Pools with to = token_out, sorted by from_token then by fee
        token_out_pools_coros = []
        for pivot in sorted_pivots:
            for fees in sorted(self.v3_pool_fees):
                token_out_pools_coros.append(self._get_v3_pool_details(pivot, token_out, fees))

        # Execute all pool queries
        all_pool_coros = direct_pool_coros + token_in_pools_coros + token_out_pools_coros
        candidate_pools = await asyncio.gather(*all_pool_coros)

        # Build paths from existing pools
        # Process direct pools
        num_direct = len(direct_pool_coros)
        for i, fees in enumerate(sorted(self.v3_pool_fees)):
            pool = candidate_pools[i]
            if pool.exists:
                v3_path_list.append(
                    V3PoolPath((V3OrderedPool(token_in, fees, token_out),), self.smart_rate_limiter)
                )

        # Process two-hop pools through pivots
        num_token_in = len(token_in_pools_coros)
        token_in_pools = candidate_pools[num_direct : num_direct + num_token_in]
        token_out_pools = candidate_pools[num_direct + num_token_in :]

        for pivot_idx, pivot in enumerate(sorted_pivots):
            # Get pools for this pivot
            pivot_in_pools = []
            pivot_out_pools = []

            for fee_idx, fees in enumerate(sorted(self.v3_pool_fees)):
                # token_in -> pivot pool
                in_pool_idx = pivot_idx * len(self.v3_pool_fees) + fee_idx
                in_pool = token_in_pools[in_pool_idx]
                if in_pool.exists:
                    pivot_in_pools.append(V3OrderedPool(token_in, fees, pivot))

                # pivot -> token_out pool
                out_pool_idx = pivot_idx * len(self.v3_pool_fees) + fee_idx
                out_pool = token_out_pools[out_pool_idx]
                if out_pool.exists:
                    pivot_out_pools.append(V3OrderedPool(pivot, fees, token_out))

            # Create two-hop paths from valid combinations
            for in_pool in pivot_in_pools:
                for out_pool in pivot_out_pools:
                    v3_path_list.append(V3PoolPath((in_pool, out_pool), self.smart_rate_limiter))

        return v3_path_list, candidate_pools

    async def get_swap_in_path(
        self, amount: Wei, token_in_address: ChecksumAddress, token_out_address: ChecksumAddress
    ) -> dict[str, Any]:
        """
        Get the best single unmixed swap path along with all candidate pools and considered tokens.

        Returns:
            Dict containing:
            - best_path: The best single path result for swapping
            - v2_candidate_pools: List of all candidate V2 pools with their details (exists, reserves, price)
            - v3_candidate_pools: List of all candidate V3 pools with their details (exists, balances, price)
            - considered_tokens: List of all considered tokens (input, output, and pivot tokens)
        """
        token_in, token_out = await asyncio.gather(
            self._get_token(token_in_address, self.w3),
            self._get_token(token_out_address, self.w3),
        )

        # Build list of all considered tokens: input, output, and pivots
        considered_tokens = [token_in, token_out]
        filtered_pivots = [pivot for pivot in self.pivots if pivot not in (token_in, token_out)]
        considered_tokens.extend(filtered_pivots)

        v2_result, v3_result = await asyncio.gather(
            self._build_v2_path_list(token_in, token_out),
            self._build_v3_path_list(token_in, token_out),
        )
        v2_pool_paths, v2_candidate_pools = v2_result
        v3_pool_paths, v3_candidate_pools = v3_result

        # Create simple paths without mixed weights
        all_paths = []

        # Add V2 paths
        for pool_path in v2_pool_paths:
            all_paths.append(WeightedPath(RouterFunction.V2_SWAP_EXACT_IN, pool_path, 100))

        # Add V3 paths
        for pool_path in v3_pool_paths:
            all_paths.append(WeightedPath(RouterFunction.V3_SWAP_EXACT_IN, pool_path, 100))

        if not all_paths:
            return {
                "best_path": WeightedPathResult(function="", path=(), weight=0, estimate=Wei(0)),
                "v2_candidate_pools": v2_candidate_pools,
                "v3_candidate_pools": v3_candidate_pools,
                "considered_tokens": considered_tokens,
            }

        # Compute path values
        computing_value_coros = [path.pool_path.get_amount_out(amount) for path in all_paths]
        path_values = await asyncio.gather(*computing_value_coros)

        # Find the best path
        best_path_index = max(range(len(path_values)), key=lambda i: path_values[i])
        best_value = path_values[best_path_index]
        best_path = all_paths[best_path_index]
        result = WeightedPathResult(
            function=best_path.router_function.value,
            path=best_path.pool_path.get_path(),
            weight=best_path.weight,
            estimate=best_value,
        )

        return {
            "best_path": result,
            "v2_candidate_pools": v2_candidate_pools,
            "v3_candidate_pools": v3_candidate_pools,
            "considered_tokens": considered_tokens,
        }
