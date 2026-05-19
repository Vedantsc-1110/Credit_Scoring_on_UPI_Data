const { ethers } = require("ethers");
require("dotenv").config();

// This service is intentionally separate from the ML pipeline.
// Existing REST API routes can import these functions to register users,
// manage consent, verify score hashes, and log credit-score access events.

const userRegistryArtifact = require("../blockchain-artifacts/contracts/UserRegistry.sol/UserRegistry.json");
const accessControlArtifact = require("../blockchain-artifacts/contracts/AccessControl.sol/AccessControl.json");
const auditLogArtifact = require("../blockchain-artifacts/contracts/AuditLog.sol/AuditLog.json");

const {
  BLOCKCHAIN_RPC_URL,
  DEPLOYER_PRIVATE_KEY,
  USER_REGISTRY_ADDRESS,
  ACCESS_CONTROL_ADDRESS,
  AUDIT_LOG_ADDRESS,
} = process.env;

function requireEnv(name, value) {
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

function getProvider() {
  return new ethers.JsonRpcProvider(requireEnv("BLOCKCHAIN_RPC_URL", BLOCKCHAIN_RPC_URL));
}

function getSigner() {
  return new ethers.Wallet(requireEnv("DEPLOYER_PRIVATE_KEY", DEPLOYER_PRIVATE_KEY), getProvider());
}

function getUserRegistryContract() {
  return new ethers.Contract(
    requireEnv("USER_REGISTRY_ADDRESS", USER_REGISTRY_ADDRESS),
    userRegistryArtifact.abi,
    getSigner(),
  );
}

function getAccessControlContract() {
  return new ethers.Contract(
    requireEnv("ACCESS_CONTROL_ADDRESS", ACCESS_CONTROL_ADDRESS),
    accessControlArtifact.abi,
    getSigner(),
  );
}

function getAuditLogContract() {
  return new ethers.Contract(
    requireEnv("AUDIT_LOG_ADDRESS", AUDIT_LOG_ADDRESS),
    auditLogArtifact.abi,
    getSigner(),
  );
}

function normalizeAddress(address, label) {
  if (!ethers.isAddress(address)) {
    throw new Error(`${label} must be a valid wallet address`);
  }
  return ethers.getAddress(address);
}

function normalizeTimestamp(expiryTimestamp) {
  const value = Number(expiryTimestamp);
  if (!Number.isSafeInteger(value) || value <= Math.floor(Date.now() / 1000)) {
    throw new Error("expiryTimestamp must be a future Unix timestamp in seconds");
  }
  return value;
}

async function registerUser(walletAddress) {
  const wallet = normalizeAddress(walletAddress, "walletAddress");
  const contract = getUserRegistryContract();
  const tx = await contract.registerUser(wallet);
  const receipt = await tx.wait();
  const user = await contract.getUser(wallet);

  return {
    transactionHash: receipt.hash,
    wallet: user.wallet,
    did: user.did,
    registeredAt: Number(user.registeredAt),
    active: user.active,
  };
}

async function grantAccess(userWallet, requesterWallet, expiryTimestamp) {
  const user = normalizeAddress(userWallet, "userWallet");
  const requester = normalizeAddress(requesterWallet, "requesterWallet");
  const expiry = normalizeTimestamp(expiryTimestamp);
  const contract = getAccessControlContract();
  const tx = await contract.grantAccess(user, requester, expiry);
  const receipt = await tx.wait();

  return {
    transactionHash: receipt.hash,
    user,
    requester,
    expiryTimestamp: expiry,
  };
}

async function revokeAccess(userWallet, requesterWallet) {
  const user = normalizeAddress(userWallet, "userWallet");
  const requester = normalizeAddress(requesterWallet, "requesterWallet");
  const contract = getAccessControlContract();
  const tx = await contract.revokeAccess(user, requester);
  const receipt = await tx.wait();

  return {
    transactionHash: receipt.hash,
    user,
    requester,
  };
}

async function checkAccess(userWallet, requesterWallet) {
  const user = normalizeAddress(userWallet, "userWallet");
  const requester = normalizeAddress(requesterWallet, "requesterWallet");
  const contract = getAccessControlContract();

  // staticCall gets the boolean for the REST API response.
  // The transaction call emits AccessAttempt for on-chain observability.
  const granted = await contract.checkAccess.staticCall(user, requester);
  const tx = await contract.checkAccess(user, requester);
  await tx.wait();
  return Boolean(granted);
}

async function logCreditAccess(requesterWallet, userWallet, result) {
  const requester = normalizeAddress(requesterWallet, "requesterWallet");
  const user = normalizeAddress(userWallet, "userWallet");
  const granted = Boolean(result);
  const contract = getAuditLogContract();
  const tx = await contract.logAccess(requester, user, granted);
  const receipt = await tx.wait();

  return {
    transactionHash: receipt.hash,
    requester,
    user,
    granted,
  };
}

async function getAuditTrail(userWallet) {
  const user = normalizeAddress(userWallet, "userWallet");
  const contract = getAuditLogContract();
  const entries = await contract.getAuditTrail(user);

  return entries.map((entry) => ({
    requester: entry.requester,
    user: entry.user,
    timestamp: Number(entry.timestamp),
    granted: entry.granted,
  }));
}

async function storeCreditScoreHash(userWallet, scoreHash) {
  const user = normalizeAddress(userWallet, "userWallet");
  if (!ethers.isHexString(scoreHash, 32)) {
    throw new Error("scoreHash must be a bytes32 hex string");
  }

  const contract = getAccessControlContract();
  const tx = await contract.setCreditScoreHash(user, scoreHash);
  const receipt = await tx.wait();

  return {
    transactionHash: receipt.hash,
    user,
    scoreHash,
  };
}

function hashCreditScorePayload(payload) {
  // Use this in the existing REST API after ML scoring.
  // Example payload: { userId, creditScore, modelVersion, scoredAt }
  return ethers.keccak256(ethers.toUtf8Bytes(JSON.stringify(payload)));
}

module.exports = {
  registerUser,
  grantAccess,
  revokeAccess,
  checkAccess,
  logCreditAccess,
  getAuditTrail,
  storeCreditScoreHash,
  hashCreditScorePayload,
};
