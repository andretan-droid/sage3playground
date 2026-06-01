#!/usr/bin/env python3
# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
import argparse
import asyncio
import logging
import sys

from web3 import AsyncWeb3

from uniswap_smart_path.smart_path import SmartPath


async def async_main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""
Uniswap Smart Path CLI Tool

Given an rpc endpoint url, this tool helps find the best path for converting
`exact-amount-in` of `token-in` to the maximum amount of `token-out`.

You can specify the locations of uniswap v2 style router and factory contracts,
uniswap v3 style quoter and factory contracts (along with selected pool fees),
or both.

You can specify a list of pivot tokens.

Then, smart path will consider all relevant direct pools, and all relevant two
hop pools using the specified pivot tokens, display all candidate pools and info
on them, and then output the best path.

Example usage:

    $ uniswap-smart-path --rpc-endpoint RPC_ENDPOINT \\
        --token-in TOKEN_IN \\
        --token-out TOKEN_OUT \\
        --exact-amount-in EXACT_AMOUNT_IN \\
        --pivot-tokens COMMA_SEPARATED_PIVOT_TOKENS \\
        --v2-factory V2_FACTORY \\
        --v2-router V2_ROUTER \\
        --v3-factory V3_FACTORY \\
        --v3-quoter V3_QUOTER \\
        --v3-pool-fees COMMA_SEPARATED_V3_POOL_FEES

    Finding best swap path for:
      Token In:  TOKEN_IN
      Token Out: TOKEN_OUT
      Exact amount In: EXACT_AMOUNT_IN atomic units

    V2 Candidate Pools:
      from=USDC to=WETH: EXISTS
        Reserves: 1000000000 / 500000000000000000
        Current price: 2000.000000
      from=USDC to=DAI: DOES NOT EXIST

    V3 Candidate Pools:
      from=USDC to=WETH fee=500: EXISTS
        TVL: 5000000000 / 2500000000000000000
        Current price: 2000.000000
      from=USDC to=WETH fee=3000: DOES NOT EXIST

    Found the best swap path.

    Uniswap version to use: V3. Sequence of V3 pools to use for swapping:

        Pool 0: from=TOKEN_IN to=TOKEN_OUT fee=500

    Estimated output: 76636730875974 atomic units
""",
    )

    # Required arguments
    parser.add_argument("--rpc-endpoint", required=True, help="RPC endpoint URL")
    parser.add_argument("--token-in", required=True, help="Input token address")
    parser.add_argument("--token-out", required=True, help="Output token address")
    parser.add_argument(
        "--exact-amount-in", required=True, type=int, help="Exact amount of input tokens (in atomic units)"
    )
    parser.add_argument(
        "--pivot-tokens", required=True, help="Comma-separated list of pivot token addresses (required)"
    )

    # V2 arguments (both must be specified together)
    parser.add_argument("--v2-factory", help="V2 factory address")
    parser.add_argument("--v2-router", help="V2 router address")

    # V3 arguments (both must be specified together)
    parser.add_argument("--v3-factory", help="V3 factory address")
    parser.add_argument(
        "--v3-quoter",
        help="V3 quoter address. You can specify the address of a V3 Quoter or a V3 QuoterV2 for this arg, both will work.",
    )
    parser.add_argument("--v3-pool-fees", help="Comma-separated list of V3 pool fees")

    # Debug flag
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    # Configure logging based on debug flag
    if args.debug:
        logging.basicConfig(
            level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    else:
        logging.basicConfig(
            level=logging.WARNING, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    # Validate that v2 params are paired
    if (args.v2_router and not args.v2_factory) or (not args.v2_router and args.v2_factory):
        print(
            "Error: --v2-factory and --v2-router are mutually dependent: either specify both or neither",
            file=sys.stderr,
        )
        sys.exit(1)

    # Validate that v3 params are together
    v3_provided = [args.v3_factory is not None, args.v3_quoter is not None, args.v3_pool_fees is not None]
    if not (all(v3_provided) or not any(v3_provided)):
        print(
            "Error: --v3-factory, --v3-quoter, and --v3-pool-fees are mutually dependent: either specify all three or none",
            file=sys.stderr,
        )
        sys.exit(1)

    # Ensure at least one protocol is specified
    if not (args.v2_factory or args.v3_factory):
        print("Error: At least one protocol (V2 or V3) must be specified", file=sys.stderr)
        sys.exit(1)

    # Parse comma-separated lists
    v3_pool_fees = None
    if args.v3_pool_fees:
        try:
            v3_pool_fees = tuple(int(fee.strip()) for fee in args.v3_pool_fees.split(","))
        except ValueError:
            print("Error: Invalid V3 pool fees format. Must be comma-separated integers", file=sys.stderr)
            sys.exit(1)

    # Parse pivot tokens (required)
    pivot_tokens = tuple(token.strip() for token in args.pivot_tokens.split(","))

    # Build kwargs for create_custom
    kwargs = {}
    if args.v2_router:
        kwargs["v2_router"] = args.v2_router
    if args.v2_factory:
        kwargs["v2_factory"] = args.v2_factory
    if args.v3_quoter:
        kwargs["v3_quoter"] = args.v3_quoter
    if args.v3_factory:
        kwargs["v3_factory"] = args.v3_factory
    if v3_pool_fees:
        kwargs["v3_pool_fees"] = v3_pool_fees
    kwargs["pivot_tokens"] = pivot_tokens  # Always include pivot_tokens since it's required

    try:
        # Create custom SmartPath instance
        smart_path = await SmartPath.create_custom(rpc_endpoint=args.rpc_endpoint, **kwargs)

        # Convert addresses to checksum format
        token_in = AsyncWeb3.to_checksum_address(args.token_in)
        token_out = AsyncWeb3.to_checksum_address(args.token_out)

        # Call get_swap_in_path_enhanced
        print("\nFinding best swap path for:")
        print(f"  Token In:  {token_in}")
        print(f"  Token Out: {token_out}")
        print(f"  Exact amount In: {args.exact_amount_in} atomic units")
        print()

        result = await smart_path.get_swap_in_path(
            amount=args.exact_amount_in, token_in_address=token_in, token_out_address=token_out
        )

        if args.v2_factory:
            # Display V2 candidate pools
            print("V2 Candidate Pools:")
            if result["v2_candidate_pools"]:
                v2_pools = result["v2_candidate_pools"]
                for pool in v2_pools:
                    if pool.exists:
                        print(
                            f"  from_symbol={pool.from_token.symbol:<7} from_address={pool.from_token.address} to_symbol={pool.to_token.symbol:<7} to_address={pool.to_token.address} exists=true from_reserve={pool.from_reserve} to_reserve={pool.to_reserve} decimal_adjusted_to_per_from_exchange_rate={pool.decimal_adjusted_to_per_from_exchange_rate:.6f}"
                        )
                    else:
                        print(
                            f"  from_symbol={pool.from_token.symbol:<7} from_address={pool.from_token.address} to_symbol={pool.to_token.symbol:<7} to_address={pool.to_token.address} exists=false"
                        )
            else:
                print("  No V2 pools found")
            print()

        if args.v3_factory:
            # Display V3 candidate pools
            print("V3 Candidate Pools:")
            if result["v3_candidate_pools"]:
                v3_pools = result["v3_candidate_pools"]
                for pool in v3_pools:
                    if pool.exists:
                        print(
                            f"  from_symbol={pool.from_token.symbol:<7} from_address={pool.from_token.address} to_symbol={pool.to_token.symbol:<7} to_address={pool.to_token.address} fee={pool.fee} exists=true from_balance={pool.from_balance} to_balance={pool.to_balance} decimal_adjusted_to_per_from_exchange_rate={pool.decimal_adjusted_to_per_from_exchange_rate:.6f}"
                        )
                    else:
                        print(
                            f"  from_symbol={pool.from_token.symbol:<7} from_address={pool.from_token.address} to_symbol={pool.to_token.symbol:<7} to_address={pool.to_token.address} fee={pool.fee} exists=false"
                        )
            else:
                print("  No V3 pools found")
            print()

        # Display best path result
        best_path = result["best_path"]
        if best_path and best_path["function"]:
            if best_path["estimate"] == 0:
                print(
                    "Paths exist, but none of them result in an output greater than 0. Maybe try a smaller or larger input amount. But also it's possible that there just aren't enough liquidity in the candidate pools for any input amount to yield any output amount greater than 0."
                )
            else:
                print("Found the best swap path.\n")
                version = "V2" if best_path["function"].startswith("V2") else "V3"
                path = best_path["path"]

                print(f"Uniswap version to use: {version}. Path:\n")

                print(f"    {path}")

                # # Helper function to get token info from address
                # def get_token_info(address):
                #     # Look for token info in candidate pools
                #     for pool in result.get('v2_candidate_pools', []) + result.get('v3_candidate_pools', []):
                #         if pool.from_token.address.lower() == address.lower():
                #             return pool.from_token.symbol, pool.from_token.address
                #         elif pool.to_token.address.lower() == address.lower():
                #             return pool.to_token.symbol, pool.to_token.address
                #     raise ValueError(f"Token address {address} not found in candidate pools")

                # if best_path['function'] == 'V2_SWAP_EXACT_IN':
                #     for i in range(0, len(path) - 1):
                #         from_symbol, from_address = get_token_info(path[i])
                #         to_symbol, to_address = get_token_info(path[i+1])
                #         print(f"    Pool {i}: from_symbol={from_symbol:<7} from_address={from_address} to_symbol={to_symbol:<7} to_address={to_address}")
                # else:
                #     for iteration, i in enumerate(range(0, len(path) - 2, 2)):
                #         from_symbol, from_address = get_token_info(path[i])
                #         to_symbol, to_address = get_token_info(path[i+2])
                #         print(f"    Pool {iteration}: from_symbol={from_symbol:<7} from_address={from_address} to_symbol={to_symbol:<7} to_address={to_address} fee={path[i+1]}")

                print(f"\nEstimated output: {best_path['estimate']} atomic units")

        else:
            print("No swap path found between the specified tokens")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Synchronous entry point for the CLI."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
