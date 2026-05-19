const hre = require("hardhat");

async function main() {
  const networkName = hre.network.name;
  if (networkName === "sepolia" && !process.env.SEPOLIA_RPC_URL) {
    throw new Error("SEPOLIA_RPC_URL is required for Sepolia deployment. Add it to .env first.");
  }
  if (networkName === "amoy" && !process.env.AMOY_RPC_URL) {
    throw new Error("AMOY_RPC_URL is required for Polygon Amoy deployment. Add it to .env first.");
  }
  if (networkName === "mumbai" && !process.env.MUMBAI_RPC_URL) {
    throw new Error("MUMBAI_RPC_URL is required for Mumbai deployment. Add it to .env first.");
  }
  if (networkName !== "hardhat" && !process.env.DEPLOYER_PRIVATE_KEY) {
    throw new Error("DEPLOYER_PRIVATE_KEY is required for testnet deployment. Add it to .env first.");
  }

  const [deployer] = await hre.ethers.getSigners();
  console.log(`Deploying blockchain layer to ${networkName} with: ${deployer.address}`);

  const UserRegistry = await hre.ethers.getContractFactory("UserRegistry");
  const userRegistry = await UserRegistry.deploy();
  await userRegistry.waitForDeployment();

  const AccessControl = await hre.ethers.getContractFactory("AccessControl");
  const accessControl = await AccessControl.deploy();
  await accessControl.waitForDeployment();

  const AuditLog = await hre.ethers.getContractFactory("AuditLog");
  const auditLog = await AuditLog.deploy();
  await auditLog.waitForDeployment();

  const userRegistryAddress = await userRegistry.getAddress();
  const accessControlAddress = await accessControl.getAddress();
  const auditLogAddress = await auditLog.getAddress();

  console.log("UserRegistry deployed to:", userRegistryAddress);
  console.log("AccessControl deployed to:", accessControlAddress);
  console.log("AuditLog deployed to:", auditLogAddress);
  console.log("");
  console.log("Add these values to .env:");
  console.log(`USER_REGISTRY_ADDRESS=${userRegistryAddress}`);
  console.log(`ACCESS_CONTROL_ADDRESS=${accessControlAddress}`);
  console.log(`AUDIT_LOG_ADDRESS=${auditLogAddress}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
