// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.13;

import {Script, console} from "forge-std/Script.sol";
import {FlawVerifier} from "../src/FlawVerifier.sol";

contract FlawVerifierScript is Script {
    function pad4(uint256 n) internal pure returns (string memory) {
        string memory s = vm.toString(n);
        if (bytes(s).length == 4) return s;
        if (bytes(s).length == 3) return string.concat("0", s);
        if (bytes(s).length == 2) return string.concat("00", s);
        if (bytes(s).length == 1) return string.concat("000", s);
        return s;
    }

    function run() public {
        uint256 initialBalance = 1_000_000 ether;
        
        console.log("Initial balance:", initialBalance / 1 ether, "ETH");
        
        vm.startBroadcast();

        FlawVerifier flawVerifier = new FlawVerifier{value: initialBalance}();

        flawVerifier.executeOnOpportunity();

        vm.stopBroadcast();

        // Shows helpful info about the final balance
        uint256 finalBalance = address(flawVerifier).balance;
        uint256 fbWhole = finalBalance / 1 ether;
        uint256 fbFrac  = (finalBalance % 1 ether) / 1e14;
        console.log(
            string.concat(
                "Final balance: ",
                vm.toString(fbWhole), ".",
                pad4(fbFrac),
                " ETH"
            )
        );

        assert(finalBalance >= 1_000_000.1 ether);
    }
}
