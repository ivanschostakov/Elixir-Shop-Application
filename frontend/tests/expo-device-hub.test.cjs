const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const { patchSource } = require("../scripts/patch-expo-device-hub.cjs");

const expoRoot = path.dirname(require.resolve("expo/package.json"));
const cliRoot = path.dirname(require.resolve("@expo/cli/package.json", { paths: [expoRoot] }));
const prerequisitePath = "start/doctor/apple/SimulatorAppPrerequisite.js";
const runningPath = "start/platforms/ios/ensureSimulatorAppRunning.js";
const managerPath = "start/platforms/ios/AppleDeviceManager.js";

class CommandError extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}

function loadPatched(relativePath, overrides) {
  const filename = path.join(cliRoot, "build/src", relativePath);
  const exports = {};
  vm.runInNewContext(patchSource(fs.readFileSync(filename, "utf8"), relativePath), {
    exports,
    require: (name) => {
      if (Object.hasOwn(overrides, name)) return overrides[name];
      if (name === "path") return path;
      if (name === "debug") return () => () => {};
      if (name === "../Prerequisite") return { Prerequisite: class {}, PrerequisiteCommandError: CommandError };
      if (name === "../DeviceManager") return { DeviceManager: class {} };
      if (name === "../../../utils/errors") return { CommandError };
      if (name === "../../../log") return { log() {}, warn() {} };
      throw new Error(`Unexpected dependency: ${name}`);
    },
  }, { filename });
  return exports;
}

function loadPrerequisite(execAsync, spawnAsync) {
  return loadPatched(prerequisitePath, {
    "@expo/osascript": { execAsync },
    "@expo/spawn-async": spawnAsync,
  }).SimulatorAppPrerequisite.instance;
}

test("SDK 54 CLI patch can be applied repeatedly", () => {
  for (const relativePath of [prerequisitePath, runningPath, managerPath]) {
    const source = fs.readFileSync(path.join(cliRoot, "build/src", relativePath), "utf8");
    const patched = patchSource(source, relativePath);
    assert.equal(patchSource(patched, relativePath), patched);
    new vm.Script(patched);
  }
  assert.throws(() => patchSource("changed upstream", prerequisitePath), /no longer matches/);
});

test("Xcode 26 Simulator and Xcode 27 Device Hub both retain the simctl check", async () => {
  for (const bundleId of ["com.apple.iphonesimulator", "com.apple.CoreSimulator.SimulatorTrampoline", "com.apple.dt.Devices"]) {
    const scripts = [];
    const commands = [];
    const prerequisite = loadPrerequisite(async (script) => {
      scripts.push(script);
      if (bundleId === "com.apple.dt.Devices" && script.includes('"Simulator"')) throw new Error("App missing");
      return bundleId;
    }, async (command, args) => {
      commands.push([command, ...args]);
      return { stdout: "" };
    });
    await prerequisite.assertImplementation();
    assert.deepEqual(commands, [["xcrun", "simctl", "help"]]);
    assert.equal(scripts.length, bundleId === "com.apple.dt.Devices" ? 2 : 1);
  }
});

test("Device Hub is found in the selected Xcode bundle when LaunchServices cannot find either app", async () => {
  const paths = [];
  const prerequisite = loadPrerequisite(async () => { throw new Error("App not registered"); }, async (command, args) => {
    if (command === "xcode-select") return { stdout: "/Volumes/Tools/Xcode.app/Contents/Developer\n" };
    if (command === "defaults") {
      paths.push(args[1]);
      if (args[1].includes("Simulator.app")) throw new Error("Missing Simulator");
      return { stdout: "com.apple.dt.Devices\n" };
    }
    return { stdout: "" };
  });
  await prerequisite.assertImplementation();
  assert.deepEqual(paths, [
    "/Volumes/Tools/Xcode.app/Contents/Developer/Applications/Simulator.app/Contents/Info.plist",
    "/Volumes/Tools/Xcode.app/Contents/Applications/DeviceHub.app/Contents/Info.plist",
  ]);
});

test("missing apps, unknown app IDs, and broken simctl still fail validation", async () => {
  const missing = async () => { throw new Error("Unavailable"); };
  await assert.rejects(loadPrerequisite(missing, missing).assertImplementation(), { code: "SIMULATOR_APP" });
  await assert.rejects(loadPrerequisite(async () => "unknown.app", missing).assertImplementation(), { code: "SIMULATOR_APP" });
  await assert.rejects(loadPrerequisite(async () => "com.apple.dt.Devices", missing).assertImplementation(), { code: "SIMCTL" });
});

test("opening a simulator falls back to Device Hub and keeps the selected device", async () => {
  for (const udid of ["test-device-id", undefined]) {
    let running = false;
    const opened = [];
    const { ensureSimulatorAppRunningAsync } = loadPatched(runningPath, {
      "@expo/osascript": { execAsync: async (script) => {
        assert.ok(script.includes('name is "DeviceHub"'));
        return running ? "1" : "0";
      } },
      "@expo/spawn-async": async (command, args) => {
        opened.push([command, ...args]);
        if (args[1] === "Simulator") throw new Error("Missing Simulator");
        running = true;
      },
      "../../../utils/delay": { waitForActionAsync: ({ action }) => action() },
    });
    await ensureSimulatorAppRunningAsync({ udid });
    assert.equal(opened.length, 2);
    assert.deepEqual(opened[1], udid ? ["open", `devices://device/open?id=${udid}`] : ["open", "-a", "DeviceHub"]);
  }
});

test("older Xcode still opens Simulator directly", async () => {
  let running = false;
  const opened = [];
  const { ensureSimulatorAppRunningAsync } = loadPatched(runningPath, {
    "@expo/osascript": { execAsync: async () => running ? "1" : "0" },
    "@expo/spawn-async": async (command, args) => {
      opened.push([command, ...args]);
      running = true;
    },
    "../../../utils/delay": { waitForActionAsync: ({ action }) => action() },
  });
  await ensureSimulatorAppRunningAsync({ udid: "legacy-device" });
  assert.deepEqual(opened, [["open", "-a", "Simulator", "--args", "-CurrentDeviceUDID", "legacy-device"]]);
});

test("window focus falls back to Device Hub without failing a successful app launch", async () => {
  for (const simulatorAvailable of [true, false]) {
    for (const hubAvailable of [true, false]) {
      const scripts = [];
      const { AppleDeviceManager } = loadPatched(managerPath, {
        "@expo/osascript": { execAsync: async (script) => {
          scripts.push(script);
          if (script.includes('"Simulator"') && !simulatorAvailable) throw new Error("Missing Simulator");
          if (script.includes('"DeviceHub"') && !hubAvailable) throw new Error("Focus unavailable");
        } },
        "./ensureSimulatorAppRunning": { ensureSimulatorAppRunningAsync: async () => {} },
        "./assertSystemRequirements": {},
        "./getBestSimulator": {},
        "./promptAppleDevice": {},
        "./simctl": {},
        "../../../utils/delay": {},
        "../../../utils/plist": {},
        "../../../utils/url": {},
        "../ExpoGoInstaller": {},
      });
      await new AppleDeviceManager().activateWindowAsync();
      assert.equal(scripts.length, simulatorAvailable ? 1 : 2);
      if (!simulatorAvailable) assert.ok(scripts[1].includes('"DeviceHub"'));
    }
  }
});
