from __future__ import annotations

import os
from typing import Any

from src.blockchain.audit import BlockchainAnchor, bytes32_hex


CREDIT_DECISION_REGISTRY_ABI: list[dict[str, Any]] = [
    {
        "inputs": [
            {"internalType": "bytes32", "name": "scoreRunHash", "type": "bytes32"},
            {"internalType": "bytes32", "name": "applicationHash", "type": "bytes32"},
            {"internalType": "bytes32", "name": "decisionHash", "type": "bytes32"},
            {"internalType": "bytes32", "name": "modelHash", "type": "bytes32"},
            {"internalType": "uint64", "name": "anchoredAt", "type": "uint64"},
        ],
        "name": "anchorDecision",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "bytes32", "name": "scoreRunHash", "type": "bytes32"},
            {"internalType": "bytes32", "name": "applicationHash", "type": "bytes32"},
            {"internalType": "bytes32", "name": "decisionHash", "type": "bytes32"},
            {"internalType": "bytes32", "name": "modelHash", "type": "bytes32"},
        ],
        "name": "verifyDecision",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
]


def publish_decision_anchor(anchor: BlockchainAnchor) -> BlockchainAnchor:
    """Submit one decision anchor transaction to an Ethereum-compatible chain."""

    try:
        from web3 import Web3
    except ImportError as exc:
        raise RuntimeError("web3 is not installed; add it before enabling blockchain publishing") from exc

    rpc_url = _required_env("ETH_RPC_URL")
    private_key = _required_env("ETH_PRIVATE_KEY")
    contract_address = _required_env("ETH_CONTRACT_ADDRESS")
    chain_id = int(_required_env("ETH_CHAIN_ID"))

    web3 = Web3(Web3.HTTPProvider(rpc_url))
    if not web3.is_connected():
        raise RuntimeError("could not connect to ETH_RPC_URL")

    account = web3.eth.account.from_key(private_key)
    contract = web3.eth.contract(
        address=web3.to_checksum_address(contract_address),
        abi=CREDIT_DECISION_REGISTRY_ABI,
    )
    anchored_at_epoch = _iso_to_epoch(anchor.anchored_at)
    transaction = contract.functions.anchorDecision(
        bytes32_hex(anchor.score_run_hash),
        bytes32_hex(anchor.application_hash),
        bytes32_hex(anchor.decision_hash),
        bytes32_hex(anchor.model_hash),
        anchored_at_epoch,
    ).build_transaction(
        {
            "from": account.address,
            "nonce": web3.eth.get_transaction_count(account.address),
            "chainId": chain_id,
        }
    )

    signed = account.sign_transaction(transaction)
    tx_hash = web3.eth.send_raw_transaction(signed.rawTransaction)

    return BlockchainAnchor(
        application_id=anchor.application_id,
        score_run_id=anchor.score_run_id,
        score_run_hash=anchor.score_run_hash,
        application_hash=anchor.application_hash,
        decision_hash=anchor.decision_hash,
        model_hash=anchor.model_hash,
        anchored_at=anchor.anchored_at,
        tx_hash=web3.to_hex(tx_hash),
        contract_address=web3.to_checksum_address(contract_address),
        chain_id=chain_id,
        status="PUBLISHED",
        error_message=None,
    )


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required when BLOCKCHAIN_ENABLED=true")
    return value


def _iso_to_epoch(value: str) -> int:
    from datetime import datetime, timezone

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp())
