// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

/// @title AccessControl
/// @notice Manages time-bound consent for lenders/banks to access credit-score hashes.
/// @dev Existing REST APIs should keep raw ML data off-chain and store only score hashes here.
contract AccessControl {
    struct Permission {
        uint64 expiryTimestamp;
        bool active;
    }

    address public owner;

    mapping(address => mapping(address => Permission)) private permissions;
    mapping(address => bytes32) private creditScoreHashes;

    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);
    event AccessGranted(address indexed user, address indexed requester, uint64 expiryTimestamp);
    event AccessRevoked(address indexed user, address indexed requester);
    event AccessAttempt(address indexed requester, address indexed user, bool granted, uint64 timestamp);
    event CreditScoreHashUpdated(address indexed user, bytes32 indexed scoreHash);

    modifier onlyOwner() {
        require(msg.sender == owner, "AccessControl: caller is not owner");
        _;
    }

    modifier onlyOwnerOrUser(address user) {
        require(msg.sender == owner || msg.sender == user, "AccessControl: not authorized");
        _;
    }

    constructor() {
        owner = msg.sender;
        emit OwnershipTransferred(address(0), msg.sender);
    }

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "AccessControl: zero owner");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }

    /// @notice Stores only a cryptographic hash of the ML-produced credit score.
    /// @dev The backend can call this after scoring; the actual score/raw features stay in the database.
    function setCreditScoreHash(address user, bytes32 scoreHash) external onlyOwner {
        require(user != address(0), "AccessControl: zero user");
        require(scoreHash != bytes32(0), "AccessControl: empty hash");
        creditScoreHashes[user] = scoreHash;
        emit CreditScoreHashUpdated(user, scoreHash);
    }

    /// @notice Grants a requester access until expiryTimestamp.
    /// @dev Users can grant consent directly; admin can also grant via the REST API service wallet.
    function grantAccess(address user, address requester, uint64 expiryTimestamp) external onlyOwnerOrUser(user) {
        require(user != address(0), "AccessControl: zero user");
        require(requester != address(0), "AccessControl: zero requester");
        require(expiryTimestamp > block.timestamp, "AccessControl: expired permission");

        permissions[user][requester] = Permission({
            expiryTimestamp: expiryTimestamp,
            active: true
        });

        emit AccessGranted(user, requester, expiryTimestamp);
    }

    /// @notice Revokes access before expiry.
    function revokeAccess(address user, address requester) external onlyOwnerOrUser(user) {
        require(requester != address(0), "AccessControl: zero requester");
        Permission storage permission = permissions[user][requester];
        require(permission.active, "AccessControl: permission inactive");

        permission.active = false;
        emit AccessRevoked(user, requester);
    }

    /// @notice Returns active consent without emitting an access attempt event.
    function hasActivePermission(address user, address requester) public view returns (bool) {
        Permission memory permission = permissions[user][requester];
        return permission.active && permission.expiryTimestamp >= block.timestamp;
    }

    /// @notice Checks access and emits an auditable access-attempt event.
    /// @dev The REST API can call this before returning a score/hash to a lender.
    function checkAccess(address user, address requester) external returns (bool granted) {
        granted = hasActivePermission(user, requester);
        emit AccessAttempt(requester, user, granted, uint64(block.timestamp));
    }

    /// @notice Lets the actual requester query the stored score hash only when consent is active.
    function getCreditScoreHash(address user) external returns (bytes32 scoreHash) {
        bool granted = hasActivePermission(user, msg.sender);
        emit AccessAttempt(msg.sender, user, granted, uint64(block.timestamp));
        require(granted, "AccessControl: access denied");
        return creditScoreHashes[user];
    }

    function getPermission(address user, address requester) external view returns (Permission memory) {
        return permissions[user][requester];
    }
}
