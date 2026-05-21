// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title CreditDecisionRegistry
/// @notice Stores tamper-evident hashes for credit scoring decisions.
/// @dev Raw applicant data, model outputs, and explanations must remain off-chain.
contract CreditDecisionRegistry {
    struct DecisionAnchor {
        bytes32 applicationHash;
        bytes32 decisionHash;
        bytes32 modelHash;
        uint64 anchoredAt;
        address writer;
        bool exists;
    }

    address public owner;
    mapping(address => bool) public authorizedWriters;
    mapping(bytes32 => DecisionAnchor) private anchors;

    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);
    event WriterAuthorizationChanged(address indexed writer, bool authorized);
    event DecisionAnchored(
        bytes32 indexed scoreRunHash,
        bytes32 indexed applicationHash,
        bytes32 indexed decisionHash,
        bytes32 modelHash,
        uint64 anchoredAt,
        address writer


        
    );

    modifier onlyOwner() {
        require(msg.sender == owner, "not owner");
        _;
    }

    modifier onlyWriter() {
        require(authorizedWriters[msg.sender], "not authorized writer");
        _;
    }

    constructor() {
        owner = msg.sender;
        authorizedWriters[msg.sender] = true;
        emit OwnershipTransferred(address(0), msg.sender);
        emit WriterAuthorizationChanged(msg.sender, true);
    }

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "new owner is zero address");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }

    function setWriter(address writer, bool authorized) external onlyOwner {
        require(writer != address(0), "writer is zero address");
        authorizedWriters[writer] = authorized;
        emit WriterAuthorizationChanged(writer, authorized);
    }

    function anchorDecision(
        bytes32 scoreRunHash,
        bytes32 applicationHash,
        bytes32 decisionHash,
        bytes32 modelHash,
        uint64 anchoredAt
    ) external onlyWriter {
        require(scoreRunHash != bytes32(0), "score hash required");
        require(!anchors[scoreRunHash].exists, "score already anchored");

        anchors[scoreRunHash] = DecisionAnchor({
            applicationHash: applicationHash,
            decisionHash: decisionHash,
            modelHash: modelHash,
            anchoredAt: anchoredAt,
            writer: msg.sender,
            exists: true
        });

        emit DecisionAnchored(
            scoreRunHash,
            applicationHash,
            decisionHash,
            modelHash,
            anchoredAt,
            msg.sender
        );
    }

    function getDecisionAnchor(bytes32 scoreRunHash) external view returns (DecisionAnchor memory) {
        require(anchors[scoreRunHash].exists, "anchor not found");
        return anchors[scoreRunHash];
    }

    function verifyDecision(
        bytes32 scoreRunHash,
        bytes32 applicationHash,
        bytes32 decisionHash,
        bytes32 modelHash
    ) external view returns (bool) {
        DecisionAnchor memory anchor = anchors[scoreRunHash];
        return (
            anchor.exists
                && anchor.applicationHash == applicationHash
                && anchor.decisionHash == decisionHash
                && anchor.modelHash == modelHash
        );
    }
}
