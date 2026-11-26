const { test } = require("node:test")
const assert = require("node:assert/strict")
const loadTs = require("./load-ts.cjs")
const policy = loadTs("screens/chat/chat-mode-policy.ts")

test("iOS exposes the same documented chat modes to every account", () => {
    assert.equal(policy.isCommunityChatAvailable("ios"), true)
    assert.equal(policy.resolveChatMode("community", "ios"), "community")
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

function renderSwitcher(platform, mode, onChange, solidStyle = false, nativeDark, inlineBadges = true, palette) {
    class Value {
        interpolate(config) { return config }
    }
    const mocks = {
        react: { useEffect: () => {}, useRef: value => ({ current: value }), useState: () => [320, () => {}] },
        "react-native": { Animated: { Value, View: "AnimatedView" }, Platform: { OS: platform }, Pressable: "Pressable", StyleSheet: { create: value => value }, Text: "Text", View: "View" },
        "@/providers/language-provider": { useLanguage: () => ({ t: key => key }) },
        "@/hooks/use-theme-styles": { useThemeStyles: factory => palette ? factory(palette) : { solidModeSwitcher: "solidTrack", solidModeSelection: "solidSelection" } },
        "@/screens/chat/community-chat-screen.styles": { createCommunityChatStyles: () => ({}) },
        "@/hooks/use-reduced-motion": { useReducedMotion: () => true },
        "@/components/platform/native-controls": { NativeChatModeControl: inlineBadges ? "NativeChatModeControl" : null },
    }
    const { AppSegmentedControl } = loadTs("components/platform/app-segmented-control.tsx", mocks)
    const { ChatModeSwitcher } = loadTs("screens/chat/chat-mode-switcher.tsx", { ...mocks,
        "@/components/platform/app-segmented-control": { AppSegmentedControl },
    })
    return AppSegmentedControl(ChatModeSwitcher({ mode, onChange, unreadCount: 5, mentorStyle: true, solidStyle, nativeDark }).props)
}

function elements(tree) {
    if (!tree || typeof tree !== "object") return []
    const children = tree.props?.children
    return [tree, ...[children].flat(Infinity).flatMap(elements)]
}

test("iOS switcher exposes working AI, community and support tabs", () => {
    const changes = []
    const nodes = elements(renderSwitcher("ios", "support", mode => changes.push(mode)))
    const tabs = nodes.filter(node => node.props?.accessibilityRole === "tab")
    assert.equal(tabs.length, 3)
    assert.equal(tabs[2].props.accessibilityState.selected, true)
    for (const [index, tab] of tabs.entries()) {
        assert.equal(tab.props.style.findLast(style => style?.flex).flex, [0.3, 0.4, 0.3][index])
        tab.props.onPress()
    }
    assert.deepEqual(changes, ["ai", "community", "support"])
    assert.ok(nodes.some(node => node.props?.children === "chat.modeGroup"))
    const indicator = nodes.find(node => node.type === "AnimatedView")
    assert.deepEqual(indicator.props.style.at(-1).width.inputRange, [0, 1, 2])
    assert.deepEqual(indicator.props.style.at(-1).width.outputRange, [312 * 0.3, 312 * 0.4, 312 * 0.3])
    assert.deepEqual(indicator.props.style.at(-1).transform[0].translateX.outputRange, [0, 312 * 0.3, 312 * (0.3 + 0.4)])
})

test("Android shows all three chat modes on a visible track in either theme", () => {
    const { darkColors, lightColors } = loadTs("theme/colors.ts", { "react-native": { Platform: { OS: "android" } } })
    for (const palette of [lightColors, darkColors]) {
        const tree = renderSwitcher("android", "support", () => {}, false, undefined, false, palette)
        const nodes = elements(tree)
        const track = tree.props.style[0]
        const indicator = nodes.find(node => node.type === "AnimatedView").props.style[0]
        assert.ok(track.backgroundColor)
        assert.notEqual(track.backgroundColor, indicator.backgroundColor)
        for (const tab of nodes.filter(node => node.props?.accessibilityRole === "tab")) {
            const text = elements(tab).find(node => node.type === "Text")
            assert.equal(text.props.children, tab.props.accessibilityLabel)
            assert.equal(text.props.style[0].color, palette.text)
        }
        assert.deepEqual(nodes.filter(node => node.props?.accessibilityRole === "tab").map(tab => tab.props.accessibilityLabel),
            ["chat.modeAi", "chat.modeGroup", "chat.modeSupport"])
    }
})

test("the solid selector highlights the admin tab without a separate overlay", () => {
    const changes = []
    const nodes = elements(renderSwitcher("ios", "community", mode => changes.push(mode), true))
    const tabs = nodes.filter(node => node.props?.accessibilityRole === "tab")
    assert.equal(tabs.length, 3)
    assert.equal(tabs[1].props.accessibilityState.selected, true)
    assert.ok(nodes[0].props.style.includes("solidTrack"))
    assert.ok(tabs[1].props.style.includes("solidSelection"))
    assert.ok(!tabs[0].props.style.includes("solidSelection"))
    assert.ok(!nodes.some(node => node.type === "BlurView" || node.type === "AnimatedView"))
    tabs[2].props.onPress()
    assert.deepEqual(changes, ["support"])
})

test("the iOS selector passes the selection and unread count to UIKit", () => {
    const changes = []
    const onChange = mode => changes.push(mode)
    const native = renderSwitcher("ios", "community", onChange, false, true)
    assert.equal(native.type, "NativeChatModeControl")
    assert.equal(native.props.selectedIndex, 1)
    assert.deepEqual(native.props.labels, ["chat.modeAi", "chat.modeGroup", "chat.modeSupport"])
    assert.deepEqual(native.props.badges, ["", "5", ""])
    native.props.onSelect({ nativeEvent: { index: 2 } })
    native.props.onSelect({ nativeEvent: { index: -1 } })
    assert.deepEqual(changes, ["support"])
})

test("native chat controls and edge blur respect the installed interface version", () => {
    for (const [platform, module] of [["ios", null], ["ios", {}], ["ios", { interfaceVersion: 2 }], ["ios", { interfaceVersion: 3 }], ["ios", { interfaceVersion: 4 }], ["ios", { interfaceVersion: 5 }], ["ios", { interfaceVersion: 6 }], ["ios", { interfaceVersion: 8 }], ["ios", { interfaceVersion: 9 }], ["ios", { interfaceVersion: 10 }], ["android", null], ["web", null]]) {
        const registeredViews = []
        const controls = loadTs("components/platform/native-controls.tsx", {
            expo: {
                requireOptionalNativeModule: () => module,
                requireNativeView: (_moduleName, viewName) => {
                    assert.ok(module)
                    registeredViews.push(viewName)
                    return viewName
                },
            },
            "react-native": { Platform: { OS: platform } },
        })
        const available = platform === "ios" && (module?.interfaceVersion ?? 0) >= 10
        assert.equal(controls.NativeChatModeControl, available ? "ModeControl" : null)
        assert.equal(controls.NativeChatAction, available ? "ActionControl" : null)
        assert.equal(controls.nativeControlsAvailable, available)
        assert.deepEqual(registeredViews, available ? ["ModeControl", "ActionControl", "ComposerMaterial", "KeyboardMaterial"] : [])
        const { AppEdgeMaterial: ChatEdgeBlur } = loadTs("components/platform/app-edge-material.tsx", {
            "@/components/platform/app-blur-surface": { AppBlurSurface: "BlurView" },
            "@/components/platform/native-controls": controls,
        })
        const style = { height: 100 }
        const blur = ChatEdgeBlur({ dark: true, topEdge: true, style })
        assert.equal(blur.type, available ? "ComposerMaterial" : "BlurView")
        assert.equal(blur.props.style, style)
    }
})

test("Android switcher still exposes the community tab", () => {
    const nodes = elements(renderSwitcher("android", "community", () => {}))
    const tabs = nodes.filter(node => node.props?.accessibilityRole === "tab")
    assert.equal(tabs.length, 3)
    assert.equal(tabs[1].props.accessibilityState.selected, true)
    assert.ok(nodes.some(node => node.props?.children === "chat.modeGroup"))
})

test("Mentor and Community are available to all native customers", () => {
    for (const platform of ["ios", "android"]) {
        assert.equal(policy.isMentorAvailable(platform), true)
        assert.equal(policy.resolveChatMode("community", platform), "community")
        const nodes = elements(renderSwitcher(platform, "community", () => {}))
        assert.equal(nodes.filter(node => node.props?.accessibilityRole === "tab").length, 3)
    }
    assert.equal(policy.isMentorAvailable("web"), false)
})

test("older installed builds keep unread counts until their native client is rebuilt", () => {
    const nodes = elements(renderSwitcher("ios", "community", () => {}, false, false, false))
    assert.equal(nodes.filter(node => node.props?.accessibilityRole === "tab").length, 3)
    assert.ok(nodes.some(node => node.props?.children === "5"))
})
