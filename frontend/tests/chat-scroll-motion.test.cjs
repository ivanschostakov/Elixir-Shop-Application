const { test } = require("node:test")
const assert = require("node:assert/strict")
const loadTs = require("./load-ts.cjs")

function useScrollHarness(t, platform = "ios", captureKeyboard = false) {
    const calls = []
    const following = []
    const frames = new Map()
    const keyboard = new Map()
    let nextFrame = 0
    const originalRequest = globalThis.requestAnimationFrame
    const originalCancel = globalThis.cancelAnimationFrame
    globalThis.requestAnimationFrame = callback => { frames.set(++nextFrame, callback); return nextFrame }
    globalThis.cancelAnimationFrame = id => frames.delete(id)
    t.after(() => { globalThis.requestAnimationFrame = originalRequest; globalThis.cancelAnimationFrame = originalCancel })
    const { useChatScroll } = loadTs("hooks/chat/use-chat-scroll.ts", {
        react: { useCallback: fn => fn, useEffect: callback => { if (captureKeyboard) { const cleanup = callback(); if (cleanup) t.after(cleanup) } }, useLayoutEffect: () => {}, useRef: value => ({ current: value }) },
        "react-native": { Platform: { OS: platform }, Keyboard: { addListener: (name, callback) => { keyboard.set(name, callback); return { remove: () => keyboard.delete(name) } } } },
        "@/screens/chat/chat-screen.constants": { CHAT_AUTO_SCROLL_BOTTOM_THRESHOLD: 56 },
    })
    const scroll = useChatScroll({ current: { scrollToEnd: options => calls.push(options) } }, null, value => following.push(value))
    const drain = () => { while (frames.size) { const pending = [...frames.values()]; frames.clear(); pending.forEach(fn => fn()) } }
    const event = (y, inset = 300) => ({ nativeEvent: { contentSize: { height: 1000 }, layoutMeasurement: { height: 700 }, contentOffset: { y }, contentInset: { bottom: inset } } })
    return { calls, following, scroll, drain, event, keyboard }
}

test("keyboard geometry does not stop following the last message and settles after opening", t => {
    const h = useScrollHarness(t, "ios", true)
    h.scroll.onScroll(h.event(300, 0))
    h.keyboard.get("keyboardWillShow")()
    h.scroll.onScroll(h.event(300, 300))
    h.scroll.onContentSizeChange()
    h.drain()
    assert.deepEqual(h.calls, [], "Native keyboard motion owns scrolling until the transition ends")
    assert.deepEqual(h.following, [], "A temporary inset is not a user scrolling away")
    h.keyboard.get("keyboardDidShow")()
    h.drain()
    assert.deepEqual(h.calls, [{ animated: false }])
})

test("opening the keyboard while reading older messages does not jump to the end", t => {
    const h = useScrollHarness(t, "ios", true)
    h.scroll.onScroll(h.event(100, 0))
    h.keyboard.get("keyboardWillShow")()
    h.keyboard.get("keyboardDidShow")()
    h.drain()
    assert.deepEqual(h.calls, [])
    assert.deepEqual(h.following, [false])
})

test("bottom tracking includes the keyboard and composer inset", t => {
    const h = useScrollHarness(t)
    h.scroll.onScroll(h.event(600))
    h.scroll.onContentSizeChange()
    h.drain()
    assert.equal(h.calls.length, 1)
    h.scroll.onScroll(h.event(300))
    assert.deepEqual(h.following, [false], "A reader 300pt above the actual end is reading history")
    h.scroll.onContentSizeChange()
    h.drain()
    assert.equal(h.calls.length, 1, "Incoming messages preserve the reader's position")
})

test("iOS layout does not schedule a competing scroll during keyboard movement", t => {
    const h = useScrollHarness(t)
    h.scroll.onLayout()
    h.drain()
    assert.deepEqual(h.calls, [])
    h.scroll.onScroll(h.event(100))
    h.scroll.followLatest(true)
    assert.deepEqual(h.following, [false, true])
    assert.deepEqual(h.calls, [{ animated: true }])
})

test("Android retains its resize-based bottom follow", t => {
    const h = useScrollHarness(t, "android")
    h.scroll.onLayout()
    h.drain()
    assert.deepEqual(h.calls, [{ animated: false }])
})

test("Android blurs only the chat material and fades the edge facing the messages", () => {
    const { AppEdgeMaterial } = loadTs("components/platform/app-edge-material.android.tsx", {
        "react-native": { ScrollView: "Fade", StyleSheet: { create: styles => styles } },
        "@/components/platform/app-blur-surface": { AppBlurSurface: "Blur" },
    })
    for (const topEdge of [true, false]) {
        const layer = AppEdgeMaterial({ dark: topEdge, topEdge, style: { height: 80 } })
        assert.deepEqual(layer.props.fadingEdgeLength, topEdge ? { start: 0, end: 32 } : { start: 32, end: 0 })
        assert.equal(layer.props.pointerEvents, "none")
        assert.equal(layer.props.scrollEnabled, false)
        assert.equal(layer.props.importantForAccessibility, "no-hide-descendants")
        assert.equal(layer.props.children.props.androidBlur, true)
        assert.equal(layer.props.children.props.tint, topEdge ? "systemUltraThinMaterialDark" : "systemUltraThinMaterialLight")
    }
})

test("every composer gets the same spacing, safe area and keyboard gap", () => {
    const { ChatComposerDock } = loadTs("components/platform/chat-layout.tsx", {
        react: { createContext: () => ({}), forwardRef: fn => fn, useContext: () => null, useEffect: () => {}, useState: () => [false, () => {}] },
        "react-native": { Platform: { OS: "ios" }, StyleSheet: { create: value => value, absoluteFillObject: { position: "absolute" } } },
        "react-native-safe-area-context": { useSafeAreaInsets: () => ({ bottom: 34 }) },
        "react-native-keyboard-controller": { KeyboardStickyView: "KeyboardStickyView" },
        "react-native-reanimated": {},
        "@/providers/theme-provider": { useTheme: () => ({ isDark: false }) },
        "@/components/platform/app-edge-material": { AppEdgeMaterial: "ChatEdgeBlur" },
    })
    for (const screenStyle of [{ paddingTop: 4 }, { paddingTop: 8, paddingHorizontal: 16 }, { paddingBottom: 90 }]) {
        const dock = ChatComposerDock({ children: "shared input", style: screenStyle }, null)
        const style = Object.assign({}, ...dock.props.style.flat(Infinity))
        assert.equal(style.paddingHorizontal, 8)
        assert.equal(style.paddingTop, 6)
        assert.equal(style.paddingBottom, 34)
        assert.deepEqual(dock.props.offset, { opened: 26 }, "34pt resting safe area becomes the same 8pt keyboard gap")
        assert.equal(dock.props.children[0].type, "ChatEdgeBlur", "All conversations use the same material layer")
    }
})
