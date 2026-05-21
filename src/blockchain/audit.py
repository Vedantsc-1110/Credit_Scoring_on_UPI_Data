from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from typing import Any


_TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class BlockchainAnchor:
    application_id: int
    score_run_id: int
    score_run_hash: str
    application_hash: str
    decision_hash: str
    model_hash: str
    anchored_at: str
    tx_hash: str | None = None
    contract_address: str | None = None
    chain_id: int | None = None
    status: str = "LOCAL_ONLY"
    error_message: str | None = None

    def to_json_payload(self) -> dict[str, Any]:
        return asdict(self)


def build_decision_anchor(
    *,
    application_id: int,
    score_run_id: int,
    application_payload_json: Any,
    score_payload_json: Any,
    model_version: str | None,
) -> BlockchainAnchor:
    """Build deterministic hashes for a scoring decision.

    The hash inputs are canonical JSON documents so the same off-chain evidence
    can be re-hashed later and compared with the Ethereum registry.
    """

    application_payload = _canonical_json(application_payload_json)
    score_payload = _canonical_json(score_payload_json)
    decision_payload = _canonical_json(
        {
            "application_id": int(application_id),
            "score_run_id": int(score_run_id),
            "score_payload": json.loads(score_payload),
        }
    )
    model_payload = _canonical_json({"model_version": model_version or ""})
    score_run_payload = _canonical_json(
        {
            "application_id": int(application_id),
            "score_run_id": int(score_run_id),
            "application_hash": _sha256_hex(application_payload),
            "decision_hash": _sha256_hex(decision_payload),
            "model_hash": _sha256_hex(model_payload),
        }
    )

    return BlockchainAnchor(
        application_id=int(application_id),
        score_run_id=int(score_run_id),
        score_run_hash=_sha256_hex(score_run_payload),
        application_hash=_sha256_hex(application_payload),
        decision_hash=_sha256_hex(decision_payload),
        model_hash=_sha256_hex(model_payload),
        anchored_at=_utc_now(),
    )


def publish_decision_anchor_if_enabled(anchor: BlockchainAnchor) -> BlockchainAnchor:
    """Publish an anchor to Ethereum when BLOCKCHAIN_ENABLED is truthy.

    Web3 is imported lazily so local development and tests can run without an
    Ethereum client or the web3 package installed.
    """

    if os.getenv("BLOCKCHAIN_ENABLED", "").strip().lower() not in _TRUE_VALUES:
        return anchor

    try:
        from src.blockchain.ethereum_client import publish_decision_anchor

        return publish_decision_anchor(anchor)
    except Exception as exc:
        return _replace_anchor(
            anchor,
            status="PUBLISH_FAILED",
            error_message=str(exc),
        )


def bytes32_hex(value: str) -> str:
    normalized = value.lower().removeprefix("0x")
    if len(normalized) != 64:
        raise ValueError("bytes32 hex value must contain 32 bytes")
    int(normalized, 16)
    return f"0x{normalized}"


def _canonical_json(value: Any) -> str:
    if isinstance(value, str):
        value = json.loads(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_hex(value: str) -> str:
    return "0x" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _replace_anchor(anchor: BlockchainAnchor, **changes: Any) -> BlockchainAnchor:
    payload = anchor.to_json_payload()
    payload.update(changes)
    return BlockchainAnchor(**payload)
