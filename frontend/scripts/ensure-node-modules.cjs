#!/usr/bin/env node

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const cwd = process.cwd();
const packageLockPath = path.join(cwd, "package-lock.json");
const nodeModulesPath = path.join(cwd, "node_modules");
const lockHashPath = path.join(nodeModulesPath, ".package-lock.hash");
const imageNodeModulesPath = "/opt/frontend-node_modules";
const requiredModules = ["expo-audio"];

function readPackageLockHash() {
  if (!fs.existsSync(packageLockPath)) {
    return null;
  }

  const lockContents = fs.readFileSync(packageLockPath);
  return crypto.createHash("sha256").update(lockContents).digest("hex");
}

function hasRequiredModules() {
  return requiredModules.every((moduleName) => {
    try {
      require.resolve(`${moduleName}/package.json`, { paths: [cwd] });
      return true;
    } catch {
      return false;
    }
  });
}

function shouldRunInstall() {
  if (!fs.existsSync(nodeModulesPath)) {
    return true;
  }

  if (!hasRequiredModules()) {
    return true;
  }

  const expectedHash = readPackageLockHash();
  if (!expectedHash) {
    return false;
  }

  if (!fs.existsSync(lockHashPath)) {
    return false;
  }

  const currentHash = fs.readFileSync(lockHashPath, "utf8").trim();
  return currentHash !== expectedHash;
}

function writeLockHash() {
  const expectedHash = readPackageLockHash();
  if (!expectedHash) {
    return;
  }

  fs.mkdirSync(nodeModulesPath, { recursive: true });
  fs.writeFileSync(lockHashPath, `${expectedHash}\n`, "utf8");
}

function runInstall() {
  console.log("Installing frontend dependencies with npm ci...");
  const result = spawnSync("npm", ["ci"], {
    cwd,
    stdio: "inherit",
  });

  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }

  writeLockHash();
}

function syncFromImageNodeModules() {
  if (!fs.existsSync(imageNodeModulesPath)) {
    return false;
  }

  console.log("Syncing frontend dependencies from Docker image cache...");
  fs.mkdirSync(nodeModulesPath, { recursive: true });
  fs.cpSync(imageNodeModulesPath, nodeModulesPath, {
    force: true,
    recursive: true,
  });
  writeLockHash();
  return true;
}

function main() {
  if (fs.existsSync(nodeModulesPath) && !fs.existsSync(lockHashPath) && hasRequiredModules()) {
    writeLockHash();
    console.log("Recorded package-lock hash for existing frontend dependencies.");
    return;
  }

  if (shouldRunInstall()) {
    if (syncFromImageNodeModules() && !shouldRunInstall()) {
      console.log("Frontend dependencies restored from image cache.");
      return;
    }

    runInstall();
    return;
  }

  console.log("Frontend dependencies are up to date.");
}

main();
