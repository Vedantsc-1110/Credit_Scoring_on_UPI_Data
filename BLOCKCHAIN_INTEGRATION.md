# Blockchain Security Layer

This project uses Ethereum as a tamper-evident audit layer for credit scoring
decisions. It does not store applicant data, model explanations, or raw score
payloads on-chain.

## What Gets Stored

SQLite remains the system of record for:

- loan application payloads
- score runs
- model decision output
- SHAP/explanation payloads
- local blockchain anchor metadata

Ethereum stores only:

- `scoreRunHash`
- `applicationHash`
- `decisionHash`
- `modelHash`
- anchor timestamp
- writer address

These hashes prove that the off-chain record has not changed after anchoring.

## New Files

- `contracts/CreditDecisionRegistry.sol`
- `src/blockchain/audit.py`
- `src/blockchain/ethereum_client.py`
- `src/blockchain/__init__.py`

## Runtime Flow

1. Analyst submits or opens an application.
2. Analyst clicks analyze.
3. Flask scores the saved payload with the loaded model artifacts.
4. The score run is saved to SQLite.
5. The app builds canonical JSON hashes for the application and decision.
6. If `BLOCKCHAIN_ENABLED=false`, the anchor is stored locally as `LOCAL_ONLY`.
7. If `BLOCKCHAIN_ENABLED=true`, the app calls `anchorDecision(...)` on the Solidity contract and stores the transaction hash.

Only saved analyst scoring is anchored. Raw `/score` API calls are intentionally
not anchored because they are not persisted as formal application decisions.

## Deploy The Contract

Use any normal Solidity toolchain such as Hardhat, Foundry, Remix, or Truffle.
Deploy:

```text
contracts/CreditDecisionRegistry.sol
```

The deployer is the initial owner and authorized writer.

For production, use a permissioned chain, private Ethereum network, Polygon
Amoy, Sepolia, or another controlled Ethereum-compatible network. Do not use a
mainnet public deployment for testing with real credit workflows.

## Configure Flask

Add these environment variables:

```powershell
$env:BLOCKCHAIN_ENABLED = "true"
$env:ETH_RPC_URL = "https://your-rpc-url"
$env:ETH_CHAIN_ID = "11155111"
$env:ETH_CONTRACT_ADDRESS = "0x..."
$env:ETH_PRIVATE_KEY = "0x..."
```

Keep `ETH_PRIVATE_KEY` out of Git. In production, prefer a signing service or
wallet/KMS integration instead of a raw private key in process environment.

## Verify A Decision

To verify a stored decision:

1. Reload the application payload and score payload from SQLite.
2. Rebuild the anchor with `build_decision_anchor(...)`.
3. Compare the rebuilt hashes with the `blockchain_anchors` SQLite row.
4. Call `verifyDecision(scoreRunHash, applicationHash, decisionHash, modelHash)` on the contract.

If both checks pass, the off-chain record matches the on-chain audit proof.

## Security Notes

- Never store PII or full credit payloads on-chain.
- Treat on-chain anchoring as integrity proof, not encryption.
- Rotate writer keys and restrict `setWriter(...)` to admin operations.
- Use a private or permissioned chain if audit metadata volume or privacy is a concern.
- Failed publish attempts are saved as `PUBLISH_FAILED` so the analyst workflow still completes.
