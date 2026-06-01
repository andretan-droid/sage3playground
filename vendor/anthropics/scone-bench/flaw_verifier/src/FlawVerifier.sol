// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.13;

contract FlawVerifier {
    constructor() payable {}
    receive() external payable {}

    function executeOnOpportunity() public {}
}
