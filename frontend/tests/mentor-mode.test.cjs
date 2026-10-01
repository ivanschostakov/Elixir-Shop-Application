const { test } = require("node:test")
const assert = require("node:assert/strict")
const loadTs = require("./load-ts.cjs")

function createMode(resolveProfileEnabled) {
    const slots = []
    let cursor = 0
    const react = {
        useState(initial) {
            const index = cursor++
            if (!(index in slots)) slots[index] = typeof initial === "function" ? initial() : initial
            return [slots[index], value => { slots[index] = typeof value === "function" ? value(slots[index]) : value }]
        },
        useRef(initial) {
            const index = cursor++
            if (!(index in slots)) slots[index] = { current: initial }
            return slots[index]
        },
        useCallback(callback, dependencies) {
            const index = cursor++
            const previous = slots[index]
            if (!previous || dependencies.some((value, i) => value !== previous.dependencies[i])) slots[index] = { callback, dependencies }
            return slots[index].callback
        },
    }
    const { useMentorMode } = loadTs("hooks/chat/use-mentor-mode.ts", { react })
    return {
        render: function Render(resolver = resolveProfileEnabled) {
            cursor = 0
            return useMentorMode(resolver)
        },
    }
}

test("hiding the mentor immediately selects ordinary AI, then showing restores the saved enabled profile", async () => {
    const profile = Object.freeze({ enabled: true, settings: Object.freeze({ reminders: true }) })
    let profileReads = 0
    const mode = createMode(async () => { profileReads++; return profile.enabled })
    const shown = mode.render()
    assert.equal(shown.shown, true)
    assert.equal(await shown.resolveEnabled(), true)
    assert.equal(profileReads, 1)

    shown.setShown(false)
    // Sending immediately after the tap must observe the new mode before React renders.
    assert.equal(await shown.resolveEnabled(), false)
    assert.equal(profileReads, 1, "Ordinary AI skips mentor profile resolution")
    const hidden = mode.render()
    assert.equal(hidden.shown, false)
    assert.equal(await hidden.resolveEnabled(), false)
    assert.equal(profileReads, 1)

    hidden.setShown(true)
    assert.equal(await hidden.resolveEnabled(), true)
    assert.equal(profileReads, 2)
    assert.equal(mode.render().shown, true)
    assert.equal(profile.enabled, true, "Visibility is presentation state, not a saved profile change")
    assert.equal(profile.settings.reminders, true)
})

test("showing the mentor does not enable a disabled profile", async () => {
    let profileReads = 0
    const mode = createMode(async () => { profileReads++; return false })
    const initial = mode.render()
    assert.equal(await initial.resolveEnabled(), false)
    initial.setShown(false)
    assert.equal(await initial.resolveEnabled(), false)
    initial.setShown(true)
    assert.equal(await initial.resolveEnabled(), false)
    assert.equal(mode.render().shown, true)
    assert.equal(profileReads, 2)
})

test("a retained send callback resolves the current profile reader after a rerender", async () => {
    const calls = []
    const mode = createMode(async () => { calls.push("old"); return true })
    const original = mode.render()
    assert.equal(await original.resolveEnabled(), true)
    const updated = mode.render(async () => { calls.push("current"); return false })
    assert.equal(updated.resolveEnabled, original.resolveEnabled)
    assert.equal(await original.resolveEnabled(), false)
    assert.deepEqual(calls, ["old", "current"])
})

test("the mentor icon shortcut retains accessible labels while switching AI modes", () => {
    const jsx = (type, props) => ({ type, props })
    const { MentorModeToggle } = loadTs("screens/chat/mentor-mode-toggle.tsx", {
        "react/jsx-runtime": { jsx, jsxs: jsx },
        "react-native": { View: "View", Text: "Text", Pressable: "Pressable", StyleSheet: { create: value => value } },
        "@/providers/language-provider": { useLanguage: () => ({ t: key => key }) },
        "@/screens/chat/mentor-ui": { MentorIcon: "MentorIcon", useMentorPalette: () => ({}) },
    })
    const mode = createMode(async () => true)
    const render = disabled => {
        const state = mode.render()
        return MentorModeToggle({ shown: state.shown, disabled, onToggle: () => state.setShown(!state.shown) })
    }
    const initial = render(false)
    const button = initial
    assert.equal(button.props.accessibilityRole, "button")
    assert.equal(button.props.accessibilityLabel, "chat.hideMentor")
    assert.deepEqual(button.props.accessibilityState, { expanded: true, disabled: false })
    button.props.onPress()
    assert.equal(button.props.children.type, "MentorIcon")
    const showButton = render(false)
    assert.equal(showButton.props.accessibilityLabel, "chat.showMentor")
    assert.deepEqual(showButton.props.accessibilityState, { expanded: false, disabled: false })
    showButton.props.onPress()
    assert.equal(render(false).props.accessibilityState.expanded, true)
    const disabledButton = render(true)
    assert.equal(disabledButton.props.disabled, true)
    assert.equal(disabledButton.props.accessibilityState.disabled, true)
})

test("AI header wrappers allow the wallpaper to show in ordinary and mentor modes", () => {
    const { createChatScreenStyles } = loadTs("screens/chat/chat-screen.styles.ts", {
        "react-native": { StyleSheet: { create: value => value, absoluteFillObject: { position: "absolute" } } },
        "@/theme/spacing": { spacing: { xs: 4, sm: 8, md: 16, lg: 24, xl: 32 } },
    })
    const styles = createChatScreenStyles({ surfaceSoft: "#FFFFFF" })
    assert.equal(styles.fixedHeader.backgroundColor, "transparent")
    assert.equal({ ...styles.fixedHeader, ...styles.mentorHeader }.backgroundColor, "transparent")
})
