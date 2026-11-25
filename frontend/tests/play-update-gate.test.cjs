const assert = require("node:assert/strict")
const test = require("node:test")
const load = require("./load-ts.cjs")

// Drive the same native state transitions as the cold-start downloader in Play build 6.
function gate(t, state, reloadAsync = async () => {}) {
    const previous = globalThis.__DEV__
    globalThis.__DEV__ = false
    t.after(() => {
        if (previous === undefined) delete globalThis.__DEV__
        else globalThis.__DEV__ = previous
    })
    let entered = false, cleanup
    const reloadStarted = { current: false }
    const { PlayUpdateGate } = load("components/navigation/play-update-gate.android.tsx", {
        expo: { requireOptionalNativeModule: () => ({ isEnabled: true }) },
        "expo-updates": { useUpdates: () => state, reloadAsync },
        react: {
            useState: () => [entered, value => { entered = value }],
            useRef: () => reloadStarted,
            useEffect: effect => { cleanup?.(); cleanup = effect() },
        },
        "react-native": { ActivityIndicator: "Spinner", Pressable: "Button", Text: "Text", View: "View", StyleSheet: { create: x => x } },
        "@/providers/language-provider": { useLanguage: () => ({ t: key => key }) },
        "@/providers/theme-provider": { useTheme: () => ({ palette: {} }) },
    })
    const root = PlayUpdateGate({ children: "shop" })
    t.after(() => cleanup?.())
    return () => root.type(root.props)
}

const current = { currentlyRunning: { updateId: "active", isEmbeddedLaunch: false }, restartCount: 0 }
const ready = { ...current, isUpdatePending: true, downloadedUpdate: { type: "new", updateId: "next" } }

test("downloads display native progress and apply the new bundle once", t => {
    const state = { ...current, isDownloading: true, downloadProgress: 0.42 }
    let reloads = 0
    const render = gate(t, state, async () => { reloads++ })
    assert.equal(render().props.children[2].props.accessibilityValue.now, 42)
    Object.assign(state, ready, { isDownloading: false })
    render(); render()
    assert.equal(reloads, 1)
})

test("entering the shop during a download defers applying it to a future launch", t => {
    const state = { ...current, isDownloading: true }
    const render = gate(t, state, () => assert.fail("should not interrupt a session"))
    render().props.children.at(-1).props.onPress()
    Object.assign(state, ready, { isDownloading: false })
    assert.equal(render().props.children, "shop")
})

test("slow or offline checks release the shop, even if an update arrives later", t => {
    t.mock.timers.enable({ apis: ["setTimeout"] })
    const state = { ...current, isChecking: true }
    const render = gate(t, state, () => assert.fail("should not reload after timeout"))
    render()
    t.mock.timers.tick(2500)
    Object.assign(state, ready, { isChecking: false })
    assert.equal(render().props.children, "shop")
})

for (const [name, event] of Object.entries({
    offline: { checkError: Error("offline") }, failedDownload: { downloadError: Error("network") },
    alreadyRunning: { ...ready, downloadedUpdate: { type: "new", updateId: "active" } },
    noNewManifest: { isUpdatePending: true }, afterReload: { ...ready, restartCount: 1 },
})) test(`startup continues on the installed bundle: ${name}`, t => {
    const render = gate(t, { ...current, ...event }, () => assert.fail("unexpected reload"))
    render()
    assert.equal(render().props.children, "shop")
})

test("a failed reload opens the installed app", async t => {
    const render = gate(t, ready, async () => { throw Error("reload failed") })
    render()
    await Promise.resolve()
    assert.equal(render().props.children, "shop")
})
