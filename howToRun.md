# How To Run: Decentralized AI-Based Credit Scoring System

This project has two main layers:

1. **ML + Flask application**
   - Runs the credit scoring UI/API.
   - Uses the existing FULL, REDUCED, and UPI models.
   - Produces a CIBIL-style score out of 900.

2. **Blockchain layer**
   - Runs separately through Hardhat.
   - Deploys smart contracts for user registry, permission-based score access, and audit logs.
   - Stores identity, consent, hashes, and access logs on-chain.
   - Does **not** store raw financial data on-chain.

Run all commands from the repository root:

```bash
cd /Users/swanandkalekar/Desktop/AI_CreditScoring
```

---

## 1. Python Environment Setup

Use the project virtual environment directly. On this Mac, the repo uses `venv/`.

```bash
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If you ever recreate the environment on macOS, use Python 3.11 ARM:

```bash
arch -arm64 /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Do **not** rely on plain `flask run` or plain `pip` if they point to a different Python version. Prefer:

```bash
python -m flask --app app run
```

---

## 2. Required Environment Variables

Create a local `.env` file from the example:

```bash
cp .env.example .env
```

Put real secrets only in `.env`, never in `.env.example`.

Minimum Flask/ML values:

```env
ARTIFACT_DIR=artifacts/
DATA_PROCESSED_DIR=data/processed/
DATA_RAW_DIR=data/raw/
EDA_PLOTS_DIR=notebooks/eda_plots/
SHAP_PLOTS_DIR=notebooks/shap_plots/
FAIRNESS_PLOTS_DIR=notebooks/fairness_plots/
EVAL_PLOTS_DIR=notebooks/eval_plots/
SQLITE_DB_PATH=data/mastermind_command_center.sqlite3
```

Blockchain values for Sepolia:

```env
SEPOLIA_RPC_URL=https://eth-sepolia.g.alchemy.com/v2/YOUR_KEY
BLOCKCHAIN_RPC_URL=https://eth-sepolia.g.alchemy.com/v2/YOUR_KEY
DEPLOYER_PRIVATE_KEY=0xYOUR_PRIVATE_KEY
USER_REGISTRY_ADDRESS=
ACCESS_CONTROL_ADDRESS=
AUDIT_LOG_ADDRESS=
```

Important:

- `.env` is hidden because the filename starts with a dot.
- `.env` is ignored by git.
- If a private key was ever placed in `.env.example`, create a new test wallet and use the new key only in `.env`.

---

## 3. Run The Flask Application

Start the app:

```bash
source venv/bin/activate
python -m flask --app app run
```

Open:

```text
http://127.0.0.1:5000
```

Useful API checks:

```bash
curl http://127.0.0.1:5000/health
```

Stop the server with `Ctrl+C`.

---

## 4. Run Tests

Run the focused API/UI tests:

```bash
python -m pytest tests/test_api.py tests/test_command_center_routes.py tests/test_command_center_smoke.py -q
```

Run the full test suite:

```bash
python -m pytest tests -q
```

---

## 5. Blockchain Setup

Install Node dependencies:

```bash
npm install
```

Compile contracts:

```bash
npm run compile
```

Contracts:

- `contracts/UserRegistry.sol`
- `contracts/AccessControl.sol`
- `contracts/AuditLog.sol`

Backend integration service:

- `services/blockchainService.js`

Hardhat build output is written to:

```text
blockchain-artifacts/
blockchain-cache/
```

This avoids mixing blockchain build files with ML model files in `artifacts/`.

---

## 6. Deploy Blockchain Locally

Use local deployment for quick testing:

```bash
npm run deploy:local
```

This deploys to Hardhat's temporary in-memory chain. The printed addresses are not permanent.

Example output:

```text
UserRegistry deployed to: 0x...
AccessControl deployed to: 0x...
AuditLog deployed to: 0x...
```

Do not use local Hardhat addresses for long-term `.env` configuration because they reset every run.

---

## 7. Deploy Blockchain To Sepolia

Before deploying, make sure `.env` contains:

```env
SEPOLIA_RPC_URL=https://eth-sepolia.g.alchemy.com/v2/YOUR_KEY
BLOCKCHAIN_RPC_URL=https://eth-sepolia.g.alchemy.com/v2/YOUR_KEY
DEPLOYER_PRIVATE_KEY=0xYOUR_PRIVATE_KEY
```

The deployer wallet must have Sepolia test ETH.

Deploy:

```bash
npm run deploy:sepolia
```

After deployment, copy the printed addresses into `.env`:

```env
USER_REGISTRY_ADDRESS=0x...
ACCESS_CONTROL_ADDRESS=0x...
AUDIT_LOG_ADDRESS=0x...
```

Then the backend blockchain service can connect to those deployed contracts.

---

## 8. Deploy Blockchain To Polygon Amoy

Mumbai is deprecated. Use Polygon Amoy for current Polygon testnet work.

In `.env`:

```env
AMOY_RPC_URL=https://polygon-amoy.g.alchemy.com/v2/YOUR_KEY
BLOCKCHAIN_RPC_URL=https://polygon-amoy.g.alchemy.com/v2/YOUR_KEY
DEPLOYER_PRIVATE_KEY=0xYOUR_PRIVATE_KEY
```

Deploy:

```bash
npm run deploy:amoy
```

Copy the printed contract addresses into `.env`.

---

## 9. What Uses ETH?

ETH/testnet tokens are used only when a blockchain transaction is sent.

ETH is used for:

- Deploying contracts with `npm run deploy:sepolia`
- Registering a user on-chain
- Granting/revoking access
- Storing a score hash
- Logging an access event

ETH is **not** used for:

- Starting Flask
- Running the ML model
- Filling a form
- Viewing the score result

In the current architecture, blockchain transactions are backend/service-wallet controlled. That means the deployer/backend wallet pays gas for blockchain actions.

---

## 10. Current Blockchain Integration Status

Implemented:

- Smart contracts
- Hardhat config
- Deployment scripts
- Ethers.js service module
- `.env` variables

Not yet wired into the Flask UI flow:

- Automatic user registration when a user submits an application
- Automatic score hash storage after ML scoring
- Automatic permission checks before showing score to a third party
- Automatic audit logging for score access
- MetaMask wallet popups

This is intentional for now because the request was to add the blockchain layer without changing the ML pipeline or frontend.

---

## 11. Optional: Run The Full Offline ML Pipeline

Only run this if you need to regenerate model/data artifacts. It requires raw datasets in `data/raw/`.

Required raw files:

- `application_train.csv`
- `application_test.csv`
- `bureau.csv`
- `bureau_balance.csv`
- `previous_application.csv`
- `installments_payments.csv`
- `POS_CASH_balance.csv`
- `credit_card_balance.csv`
- `final_base_with_upi_corrected.csv` for the standalone UPI model

Run:

```bash
python -m src.data_pipeline
python -m src.feature_engineering
python -m src.models.train
python -m src.models.upi
python -m src.fairness_audit
```

Skip `src.models.upi` if you only want the original FULL/REDUCED artifacts.

Expected important artifacts:

- `artifacts/full_feature_builder.joblib`
- `artifacts/full_model.joblib`
- `artifacts/full_calibrator.joblib`
- `artifacts/reduced_feature_builder.joblib`
- `artifacts/reduced_model.joblib`
- `artifacts/reduced_calibrator.joblib`
- `artifacts/upi_feature_builder.joblib`
- `artifacts/upi_model.joblib`
- `artifacts/upi_calibrator.joblib`
- `artifacts/model_fairness_audit_passed.joblib`

---

## 12. Troubleshooting

### `ModuleNotFoundError: No module named 'seaborn'`

You are probably using the wrong Python interpreter.

Use:

```bash
source venv/bin/activate
python -m pip install -r requirements.txt
python -m flask --app app run
```

### `Error HH100: Network sepolia doesn't exist`

Use the updated `hardhat.config.js`. Then ensure `.env` has:

```env
SEPOLIA_RPC_URL=...
DEPLOYER_PRIVATE_KEY=...
```

### `SEPOLIA_RPC_URL is required`

Your `.env` is missing the Sepolia RPC URL or Hardhat cannot read it.

Check:

```bash
ls -la .env
```

### MetaMask Does Not Pop Up

This is expected.

The current blockchain layer uses backend/Hardhat signing through `DEPLOYER_PRIVATE_KEY`. MetaMask popups only happen if the frontend is changed to use `window.ethereum`, which is not part of the current integration.

### `npm audit` shows vulnerabilities

Hardhat projects commonly show dependency audit warnings. For a local academic prototype, do not blindly run force fixes. Use:

```bash
npm audit
```

and review before changing versions.
