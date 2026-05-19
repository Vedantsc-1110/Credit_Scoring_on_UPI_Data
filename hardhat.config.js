require("dotenv").config();
require("@nomicfoundation/hardhat-ethers");

const { SEPOLIA_RPC_URL, AMOY_RPC_URL, MUMBAI_RPC_URL, DEPLOYER_PRIVATE_KEY } = process.env;

const accounts = DEPLOYER_PRIVATE_KEY ? [DEPLOYER_PRIVATE_KEY] : [];
const networks = {
  hardhat: {},
  sepolia: {
    url: SEPOLIA_RPC_URL || "http://127.0.0.1:8545",
    accounts,
  },
  amoy: {
    url: AMOY_RPC_URL || "http://127.0.0.1:8545",
    accounts,
  },
};

if (MUMBAI_RPC_URL) {
  networks.mumbai = {
    url: MUMBAI_RPC_URL,
    accounts,
  };
}

module.exports = {
  solidity: {
    version: "0.8.24",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200,
      },
    },
  },
  networks,
  paths: {
    sources: "./contracts",
    tests: "./blockchain-test",
    cache: "./blockchain-cache",
    artifacts: "./blockchain-artifacts",
  },
};
