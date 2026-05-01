#!/usr/bin/env node
/* global __dirname */

const { execFileSync, spawnSync } = require("node:child_process");
const path = require("node:path");

const MAX_ANDROID_JAVA_MAJOR = 24;
const PREFERRED_ANDROID_JAVA_VERSIONS = ["21", "17"];

function loadExpoCliExport(modulePath, exportName) {
  const candidates = [
    `@expo/cli/build/src/${modulePath}`,
    path.join(__dirname, "../node_modules/expo/node_modules/@expo/cli/build/src", modulePath),
  ];
  const errors = [];

  for (const candidate of candidates) {
    try {
      return require(candidate)[exportName];
    } catch (error) {
      errors.push(error);
    }
  }

  const errorMessages = errors
    .map((error) => (error instanceof Error ? error.message : String(error)))
    .join("\n");

  throw new Error(
    [
      `Unable to load Expo CLI export "${exportName}" from "${modulePath}".`,
      "Run `npm install` in the frontend directory, then try the command again.",
      errorMessages,
    ].join("\n")
  );
}

const COMMAND_LOADERS = {
  start: () => loadExpoCliExport("start/index.js", "expoStart"),
  "run:android": () => loadExpoCliExport("run/android/index.js", "expoRunAndroid"),
  "run:ios": () => loadExpoCliExport("run/ios/index.js", "expoRunIos"),
  export: () => loadExpoCliExport("export/index.js", "expoExport"),
  prebuild: () => loadExpoCliExport("prebuild/index.js", "expoPrebuild"),
};

function printUsage() {
  console.error(
    [
      "Usage: node scripts/expo-cli.cjs <command> [...args]",
      "",
      "Supported commands:",
      "  start",
      "  run:android",
      "  run:ios",
      "  export",
      "  prebuild",
    ].join("\n")
  );
}

function getJavaMajor(javaCommand, env = process.env) {
  const result = spawnSync(javaCommand, ["-version"], { encoding: "utf8", env });
  const output = `${result.stdout ?? ""}${result.stderr ?? ""}`;
  const match = output.match(/version "(\d+)/);
  return match ? Number(match[1]) : null;
}

function prependJavaToPath(javaHome) {
  const javaBin = path.join(javaHome, "bin");
  const pathEntries = (process.env.PATH ?? "")
    .split(path.delimiter)
    .filter(Boolean)
    .filter((entry) => entry !== javaBin);

  process.env.PATH = [javaBin, ...pathEntries].join(path.delimiter);
}

function resolveMacJavaHome(version) {
  try {
    return execFileSync("/usr/libexec/java_home", ["-v", version], {
      encoding: "utf8",
    }).trim();
  } catch {
    return null;
  }
}

function configureAndroidJava(command) {
  if (command !== "run:android") {
    return;
  }

  const explicitJavaHome = process.env.EXPO_ANDROID_JAVA_HOME?.trim();
  if (explicitJavaHome) {
    process.env.JAVA_HOME = explicitJavaHome;
    prependJavaToPath(explicitJavaHome);
    return;
  }

  const currentJavaMajor = getJavaMajor("java");
  if (currentJavaMajor !== null && currentJavaMajor <= MAX_ANDROID_JAVA_MAJOR) {
    return;
  }

  if (process.platform !== "darwin") {
    if (currentJavaMajor !== null) {
      console.warn(
        `Android build is using Java ${currentJavaMajor}. Set JAVA_HOME to JDK 21 or 17 if Gradle fails.`
      );
    }
    return;
  }

  const compatibleJavaHome = PREFERRED_ANDROID_JAVA_VERSIONS.map(resolveMacJavaHome).find(Boolean);
  if (!compatibleJavaHome) {
    if (currentJavaMajor !== null) {
      console.warn(
        `Android build is using Java ${currentJavaMajor}, but no compatible macOS JDK 21/17 installation was found.`
      );
    }
    return;
  }

  process.env.JAVA_HOME = compatibleJavaHome;
  prependJavaToPath(compatibleJavaHome);

  const configuredJavaMajor =
    getJavaMajor(path.join(compatibleJavaHome, "bin", "java")) ?? "compatible";
  console.log(`Using JDK ${configuredJavaMajor} for Android build: ${compatibleJavaHome}`);
}

async function main() {
  const [command, ...args] = process.argv.slice(2);

  if (!command) {
    printUsage();
    process.exitCode = 1;
    return;
  }

  const loadCommand = COMMAND_LOADERS[command];
  if (!loadCommand) {
    console.error(`Unsupported Expo command: ${command}`);
    printUsage();
    process.exitCode = 1;
    return;
  }

  configureAndroidJava(command);

  const runCommand = loadCommand();
  await runCommand(args);
}

main().catch((error) => {
  const message = error instanceof Error ? error.stack ?? error.message : String(error);
  console.error(message);
  process.exit(1);
});
