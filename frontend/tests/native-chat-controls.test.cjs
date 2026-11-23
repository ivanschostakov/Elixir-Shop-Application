const assert = require("node:assert/strict")
const test = require("node:test")
const load = require("./load-ts.cjs")
const fs = require("node:fs")

test("every JS native view is registered exactly once in the Expo module", () => {
    const nativeSource = fs.readFileSync(require.resolve("../modules/elixir-chat-controls/ios/ElixirChatControlsModule.swift"), "utf8")
    const names = [...nativeSource.matchAll(/ViewName\("([^"]+)"\)/g)].map(match => match[1])
    assert.equal(new Set(names).size, names.length, "Expo traps at startup if two views have the same name")
    const requested = []
    load("components/platform/native-controls.tsx", {
        expo: {
            requireOptionalNativeModule: () => ({ interfaceVersion: 10 }),
            requireNativeView: (_module, name) => { requested.push(name); return name },
        },
        "react-native": { Platform: { OS: "ios" } },
    })
    assert.deepEqual(names.sort(), requested.sort(), "The JS bridge must request only registered native views")
})

for (const nativeModule of [null, {}, { interfaceVersion: 7 }, { interfaceVersion: 8 }, { interfaceVersion: 9 }]) {
    test(`restored chat uses JS controls when the installed native interface is ${JSON.stringify(nativeModule)}`, () => {
        const controls = load("components/platform/native-controls.tsx", {
            expo: {
                requireOptionalNativeModule: () => nativeModule,
                requireNativeView: () => { throw Error("An older binary cannot provide the new view") },
            },
            "react-native": { Platform: { OS: "ios" } },
        })
        assert.ok(Object.entries(controls).filter(([name]) => name.startsWith("Native")).every(([, control]) => control === null))
        assert.equal(controls.nativeControlsAvailable, false)
    })
}

test("the restored iOS interface provides modes, voice actions and support controls", () => {
    const views = []
    const controls = load("components/platform/native-controls.tsx", {
        expo: {
            requireOptionalNativeModule: () => ({ interfaceVersion: 10 }),
            requireNativeView: (_module, name) => { views.push(name); return name },
        },
        "react-native": { Platform: { OS: "ios" } },
    })
    assert.equal(controls.NativeChatAction, "ActionControl")
    assert.deepEqual(views, ["ModeControl", "ActionControl", "ComposerMaterial", "KeyboardMaterial"])
    assert.equal(controls.nativeControlsAvailable, true)
})

test("Android does not try to load iOS native controls", () => {
    const controls = load("components/platform/native-controls.tsx", {
        expo: { requireOptionalNativeModule: () => { throw Error("iOS only") } },
        "react-native": { Platform: { OS: "android" } },
    })
    assert.ok(Object.entries(controls).filter(([name]) => name.startsWith("Native")).every(([, control]) => control === null))
})
