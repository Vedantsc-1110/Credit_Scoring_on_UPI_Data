// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

/// @title UserRegistry
/// @notice Registers wallet-based DID-like identities for the credit scoring system.
/// @dev The ML/API layer can call this after a user creates an account in the off-chain app.
contract UserRegistry {
    struct UserRecord {
        address wallet;
        bytes32 did;
        uint64 registeredAt;
        bool active;
        bool exists;
    }

    address public owner;
    mapping(address => UserRecord) private users;

    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);
    event UserRegistered(address indexed wallet, bytes32 indexed did, uint64 registeredAt);
    event UserStatusChanged(address indexed wallet, bool active);

    modifier onlyOwner() {
        require(msg.sender == owner, "UserRegistry: caller is not owner");
        _;
    }

    modifier onlyOwnerOrUser(address wallet) {
        require(msg.sender == owner || msg.sender == wallet, "UserRegistry: not authorized");
        _;
    }

    constructor() {
        owner = msg.sender;
        emit OwnershipTransferred(address(0), msg.sender);
    }

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "UserRegistry: zero owner");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }

    /// @notice Registers a user wallet and creates a deterministic DID-like record.
    /// @dev Allows the user wallet or backend admin wallet to register. Raw user data remains off-chain.
    function registerUser(address wallet) external returns (bytes32 did) {
        require(wallet != address(0), "UserRegistry: zero wallet");
        require(msg.sender == owner || msg.sender == wallet, "UserRegistry: not authorized");
        require(!users[wallet].exists, "UserRegistry: already registered");

        did = keccak256(abi.encodePacked("did:ai-credit:", block.chainid, address(this), wallet));
        users[wallet] = UserRecord({
            wallet: wallet,
            did: did,
            registeredAt: uint64(block.timestamp),
            active: true,
            exists: true
        });

        emit UserRegistered(wallet, did, uint64(block.timestamp));
    }

    /// @notice Deactivates a registered account.
    /// @dev Only the account owner or contract admin can deactivate.
    function deactivateUser(address wallet) external onlyOwnerOrUser(wallet) {
        require(users[wallet].exists, "UserRegistry: not registered");
        require(users[wallet].active, "UserRegistry: already inactive");
        users[wallet].active = false;
        emit UserStatusChanged(wallet, false);
    }

    /// @notice Reactivates an account when the off-chain API/admin approves reinstatement.
    function reactivateUser(address wallet) external onlyOwner {
        require(users[wallet].exists, "UserRegistry: not registered");
        require(!users[wallet].active, "UserRegistry: already active");
        users[wallet].active = true;
        emit UserStatusChanged(wallet, true);
    }

    function getUser(address wallet) external view returns (UserRecord memory) {
        return users[wallet];
    }

    function isActive(address wallet) external view returns (bool) {
        return users[wallet].exists && users[wallet].active;
    }
}
