// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

/// @title AuditLog
/// @notice Append-only audit trail for credit-score access attempts.
/// @dev The REST API should log each granted/denied score access after checking permissions.
contract AuditLog {
    struct LogEntry {
        address requester;
        address user;
        uint64 timestamp;
        bool granted;
    }

    address public owner;
    LogEntry[] private logs;
    mapping(address => uint256[]) private userLogIndexes;
    mapping(address => bool) public authorizedLoggers;

    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);
    event LoggerAuthorizationChanged(address indexed logger, bool authorized);
    event CreditAccessLogged(
        uint256 indexed logId,
        address indexed requester,
        address indexed user,
        bool granted,
        uint64 timestamp
    );

    modifier onlyOwner() {
        require(msg.sender == owner, "AuditLog: caller is not owner");
        _;
    }

    modifier onlyAuthorizedLogger() {
        require(authorizedLoggers[msg.sender], "AuditLog: not authorized logger");
        _;
    }

    constructor() {
        owner = msg.sender;
        authorizedLoggers[msg.sender] = true;
        emit OwnershipTransferred(address(0), msg.sender);
        emit LoggerAuthorizationChanged(msg.sender, true);
    }

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "AuditLog: zero owner");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }

    /// @notice Authorizes the existing REST API signer or AccessControl contract to append audit records.
    function setAuthorizedLogger(address logger, bool authorized) external onlyOwner {
        require(logger != address(0), "AuditLog: zero logger");
        authorizedLoggers[logger] = authorized;
        emit LoggerAuthorizationChanged(logger, authorized);
    }

    /// @notice Appends a public, immutable record of an access attempt.
    function logAccess(address requester, address user, bool granted) external onlyAuthorizedLogger returns (uint256 logId) {
        require(requester != address(0), "AuditLog: zero requester");
        require(user != address(0), "AuditLog: zero user");

        logId = logs.length;
        logs.push(LogEntry({
            requester: requester,
            user: user,
            timestamp: uint64(block.timestamp),
            granted: granted
        }));
        userLogIndexes[user].push(logId);

        emit CreditAccessLogged(logId, requester, user, granted, uint64(block.timestamp));
    }

    function getAuditTrail(address user) external view returns (LogEntry[] memory) {
        uint256[] storage indexes = userLogIndexes[user];
        LogEntry[] memory trail = new LogEntry[](indexes.length);

        for (uint256 i = 0; i < indexes.length; i++) {
            trail[i] = logs[indexes[i]];
        }

        return trail;
    }

    function getLogCount() external view returns (uint256) {
        return logs.length;
    }
}
