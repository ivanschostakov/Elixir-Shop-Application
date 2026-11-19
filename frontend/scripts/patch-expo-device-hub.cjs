#!/usr/bin/env node
/* global __dirname */

const fs = require("node:fs");
const path = require("node:path");

// Backport Device Hub support to the SDK 54 CLI. Xcode 27 moved its apps to
// Contents/Applications and replaced Simulator.app with DeviceHub.app.
// https://github.com/expo/expo/issues/46882
const replacements = {
  "start/doctor/apple/SimulatorAppPrerequisite.js": [
    [
      `return (await (0, _osascript().execAsync)('id of app "Simulator"')).trim();`,
      `return (await (0, _osascript().execAsync)('id of app "Simulator"').catch(() =>
            (0, _osascript().execAsync)('id of app "DeviceHub"'))).trim();`,
    ],
    [
      `const { stdout: bundleId } = await (0, _spawnasync().default)('defaults', [
            'read',
            simulatorInfoPlist,
            'CFBundleIdentifier'
        ]);`,
      `const readBundleId = (infoPlist) => (0, _spawnasync().default)('defaults', [
            'read', infoPlist, 'CFBundleIdentifier'
        ]);
        const { stdout: bundleId } = await readBundleId(simulatorInfoPlist).catch(() =>
            readBundleId(_path().default.join(developerDir.trim(), '..', 'Applications', 'DeviceHub.app', 'Contents', 'Info.plist')));`,
    ],
    [
      `result !== 'com.apple.iphonesimulator' && result !== 'com.apple.CoreSimulator.SimulatorTrampoline'`,
      `result !== 'com.apple.iphonesimulator' && result !== 'com.apple.CoreSimulator.SimulatorTrampoline' && result !== 'com.apple.dt.Devices'`,
    ],
    [
      `Can't determine id of Simulator app; the Simulator is most likely not installed on this machine.`,
      `Can't determine id of Device Hub or Simulator app; Device Hub or Simulator is most likely not installed on this machine.`,
    ],
  ],
  "start/platforms/ios/ensureSimulatorAppRunning.js": [
    [
      `count processes whose name is "Simulator"'`,
      `count processes whose name is "Simulator" or name is "DeviceHub"'`,
    ],
    [
      `await (0, _spawnasync().default)('open', args);`,
      `try {
        await (0, _spawnasync().default)('open', args);
    } catch {
        const deviceHubArgs = device.udid
            ? [\`devices://device/open?id=\${encodeURIComponent(device.udid)}\`]
            : ['-a', 'DeviceHub'];
        await (0, _spawnasync().default)('open', deviceHubArgs);
    }`,
    ],
  ],
  "start/platforms/ios/AppleDeviceManager.js": [
    [
      `await _osascript().execAsync(\`tell application "Simulator" to activate\`);`,
      `try {
            await _osascript().execAsync(\`tell application "Simulator" to activate\`);
        } catch {
            await _osascript().execAsync(\`tell application "DeviceHub" to activate\`).catch((error) => {
                // Focusing the window must not fail an already successful app launch.
                debug('Unable to focus Device Hub: %s', error.message);
            });
        }`,
    ],
  ],
};

function patchSource(contents, relativePath) {
  for (const [before, after] of replacements[relativePath]) {
    if (contents.includes(after)) {
      continue;
    }
    if (!contents.includes(before)) {
      throw new Error(`Expo Device Hub patch no longer matches ${relativePath}; review the installed CLI before updating this patch.`);
    }
    contents = contents.replace(before, after);
  }
  return contents;
}

function patchExpoDeviceHub(projectRoot = path.resolve(__dirname, "..")) {
  const expoRoot = path.dirname(require.resolve("expo/package.json", { paths: [projectRoot] }));
  const cliPackagePath = require.resolve("@expo/cli/package.json", { paths: [expoRoot] });
  const { version } = JSON.parse(fs.readFileSync(cliPackagePath, "utf8"));
  if (!version.startsWith("54.")) {
    console.log(`Expo CLI ${version}: skipping the SDK 54 Device Hub patch`);
    return;
  }

  const sourceRoot = path.join(path.dirname(cliPackagePath), "build", "src");
  // Validate every replacement before writing so an upstream change cannot leave
  // a partially patched CLI. Reapplying this after npm install is safe.
  const updates = Object.keys(replacements).map((relativePath) => {
    const filePath = path.join(sourceRoot, relativePath);
    const original = fs.readFileSync(filePath, "utf8");
    return { filePath, original, patched: patchSource(original, relativePath) };
  });
  for (const { filePath, original, patched } of updates) {
    if (original !== patched) {
      fs.writeFileSync(filePath, patched);
    }
  }
  console.log(`Expo CLI ${version}: Device Hub compatibility patch applied`);
}

module.exports = { patchExpoDeviceHub, patchSource };

if (require.main === module) {
  patchExpoDeviceHub();
}
