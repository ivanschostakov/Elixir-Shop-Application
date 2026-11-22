const assert = require("node:assert/strict")
const test = require("node:test")
const load = require("./load-ts.cjs")

for (const nativeModule of [null, {}, { interfaceVersion: 7 }]) {
    test(`support uses JS controls when the installed native interface is ${JSON.stringify(nativeModule)}`, () => {
        const controls = load("screens/chat/native-chat-controls.tsx", {
            expo: {
                requireOptionalNativeModule: () => nativeModule,
                requireNativeView: () => { throw Error("An older binary cannot provide the new view") },
            },
            "react-native": { Platform: { OS: "ios" } },
        })
        assert.ok(Object.values(controls).every(control => control === null))
    })
}

test("the current iOS interface provides every support control", () => {
    const views = []
    const controls = load("screens/chat/native-chat-controls.tsx", {
        expo: {
            requireOptionalNativeModule: () => ({ interfaceVersion: 8 }),
            requireNativeView: (_module, name) => { views.push(name); return name },
        },
        "react-native": { Platform: { OS: "ios" } },
    })
    assert.equal(controls.NativeChatTitleMaterial, "TitleMaterial")
    assert.deepEqual(views, ["ActionControl", "ComposerMaterial", "InputMaterial", "MenuControl", "TitleMaterial"])
})

test("Android does not try to load iOS native controls", () => {
    const controls = load("screens/chat/native-chat-controls.tsx", {
        expo: { requireOptionalNativeModule: () => { throw Error("iOS only") } },
        "react-native": { Platform: { OS: "android" } },
    })
    assert.ok(Object.values(controls).every(control => control === null))
})
