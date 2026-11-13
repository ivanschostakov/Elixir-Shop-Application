const { test } = require("node:test")
const assert = require("node:assert/strict")
const loadTs = require("./load-ts.cjs")
const policy = loadTs("screens/chat/chat-mode-policy.ts")

test("iOS normalizes old community links and stored selections to AI", () => {
    assert.equal(policy.isCommunityChatAvailable("ios"), false)
    assert.equal(policy.resolveChatMode("community", "ios"), "ai")
    assert.equal(policy.resolveChatMode("ai", "ios"), "ai")
    assert.equal(policy.resolveChatMode("support", "ios"), "support")
    assert.equal(policy.resolveChatMode("unknown", "ios"), null)
    assert.equal(policy.resolveChatMode(null, "ios"), null)
})

test("Android and web retain all existing chat modes", () => {
    for (const platform of ["android", "web"]) {
        assert.equal(policy.isCommunityChatAvailable(platform), true)
        for (const mode of ["ai", "community", "support"]) {
            assert.equal(policy.resolveChatMode(mode, platform), mode)
        }
    }
})

function renderSwitcher(platform, mode, onChange, privateIosFeatures = false, glass = false) {
    class Value {
        interpolate(config) { return config }
    }
    const { ChatModeSwitcher } = loadTs("screens/chat/chat-mode-switcher.tsx", {
        react: { useEffect: () => {}, useRef: value => ({ current: value }), useState: () => [320, () => {}] },
        "react-native": { Animated: { Value, View: "AnimatedView" }, Platform: { OS: platform }, Pressable: "Pressable", StyleSheet: { create: value => value }, Text: "Text", View: "View" },
        "@/providers/language-provider": { useLanguage: () => ({ t: key => key }) },
        "expo-blur": { BlurView: "BlurView" },
        "@/hooks/use-theme-styles": { useThemeStyles: () => ({}) },
        "@/screens/chat/community-chat-screen.styles": { createCommunityChatStyles: () => ({}) },
        "@/screens/chat/chat-mode-transition": { useChatReducedMotion: () => true },
        "@/screens/chat/chat-mode-policy": policy,
    })
    return ChatModeSwitcher({ mode, onChange, unreadCount: 5, mentorStyle: true, privateIosFeatures, glassTint: glass ? "systemThinMaterial" : undefined })
}

function elements(tree) {
    if (!tree || typeof tree !== "object") return []
    const children = tree.props?.children
    return [tree, ...[children].flat(Infinity).flatMap(elements)]
}

test("iOS switcher has only AI and support with equal-width working tabs", () => {
    const changes = []
    const nodes = elements(renderSwitcher("ios", "support", mode => changes.push(mode)))
    const tabs = nodes.filter(node => node.props?.accessibilityRole === "tab")
    assert.equal(tabs.length, 2)
    assert.equal(tabs[1].props.accessibilityState.selected, true)
    for (const tab of tabs) {
        assert.equal(tab.props.style.at(-1).flex, 0.5)
        tab.props.onPress()
    }
    assert.deepEqual(changes, ["ai", "support"])
    assert.ok(!nodes.some(node => node.props?.children === "chat.modeGroup"))
    const indicator = nodes.find(node => node.type === "AnimatedView")
    assert.deepEqual(indicator.props.style.at(-1).width.inputRange, [0, 1])
    assert.deepEqual(indicator.props.style.at(-1).width.outputRange, [156, 156])
    assert.deepEqual(indicator.props.style.at(-1).transform[0].translateX.outputRange, [0, 156])
})

test("the glass selector retains the admin tabs and switches modes", () => {
    const changes = []
    const nodes = elements(renderSwitcher("ios", "community", mode => changes.push(mode), true, true))
    const tabs = nodes.filter(node => node.props?.accessibilityRole === "tab")
    assert.equal(tabs.length, 3)
    assert.equal(tabs[1].props.accessibilityState.selected, true)
    assert.ok(nodes.some(node => node.type === "BlurView"))
    tabs[2].props.onPress()
    assert.deepEqual(changes, ["support"])
})

test("Android switcher still exposes the community tab", () => {
    const nodes = elements(renderSwitcher("android", "community", () => {}))
    const tabs = nodes.filter(node => node.props?.accessibilityRole === "tab")
    assert.equal(tabs.length, 3)
    assert.equal(tabs[1].props.accessibilityState.selected, true)
    assert.ok(nodes.some(node => node.props?.children === "chat.modeGroup"))
})

test("only the privileged iOS account can open Mentor and Community", () => {
    assert.equal(policy.isMentorAvailable("ios"), false)
    assert.equal(policy.isMentorAvailable("ios", true), true)
    assert.equal(policy.isMentorAvailable("android"), true)
    assert.equal(policy.isMentorAvailable("web", true), false)
    assert.equal(policy.resolveChatMode("community", "ios", true), "community")
    const nodes = elements(renderSwitcher("ios", "community", () => {}, true))
    assert.equal(nodes.filter(node => node.props?.accessibilityRole === "tab").length, 3)
})
