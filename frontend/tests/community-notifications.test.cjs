const { test } = require("node:test")
const assert = require("node:assert/strict")
const loadTs = require("./load-ts.cjs")
const blocks = loadTs("hooks/chat/community-blocks.ts")
const initial = { muted: false, muted_topic_ids: [] }
const response = notifications => ({ topics: [], total_unread: 4, blocked_author_ids: [], notifications })
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
const flush = () => new Promise(resolve => setImmediate(resolve))

function harness() {
    const slots = [], effects = []
    let cursor = 0, nextTopics = Promise.resolve(response(initial)), nextUpdate = Promise.resolve(initial)
    const writes = []
    const react = {
        useState(initial) { const i = cursor++; if (!(i in slots)) slots[i] = typeof initial === "function" ? initial() : initial; return [slots[i], value => { slots[i] = typeof value === "function" ? value(slots[i]) : value }] },
        useRef(initial) { const i = cursor++; if (!(i in slots)) slots[i] = { current: initial }; return slots[i] },
        useCallback(callback, deps) { const i = cursor++; if (!slots[i] || deps.some((value, j) => value !== slots[i].deps[j])) slots[i] = { deps, callback }; return slots[i].callback },
        useEffect(callback, deps) { const i = cursor++; if (!slots[i] || deps.some((value, j) => value !== slots[i].deps[j])) effects.push(() => { slots[i]?.cleanup?.(); slots[i] = { deps, cleanup: callback() } }) },
    }
    const { useCommunityChat } = loadTs("hooks/chat/use-community-chat.ts", {
        react, "react-native": { AppState: { currentState: "active", addEventListener: () => ({ remove() {} }) } },
        "@react-navigation/native": { useIsFocused: () => false },
        "@/hooks/chat/community-blocks": blocks,
        "@/services/api/community": { getCommunityStatus: async () => ({ enabled: true, access: "granted" }), getCommunityTopics: () => nextTopics, setCommunityNotificationsMuted: (...args) => { writes.push(args); return nextUpdate } },
    })
    return {
        writes,
        topics(value) { nextTopics = value }, update(value) { nextUpdate = value },
        render: function Render() { cursor = 0; const result = useCommunityChat(false); effects.splice(0).forEach(run => run()); return result },
        unmount() { slots.forEach(slot => slot?.cleanup?.()) },
    }
}

test("group and topic notification switches use scoped authenticated PATCH routes", async () => {
    const calls = []
    const api = loadTs("services/api/community.ts", { "@/services/api/client": { apiPatch: async (...args) => calls.push(args) } })
    await api.setCommunityNotificationsMuted(true)
    await api.setCommunityNotificationsMuted(false, 7)
    assert.deepEqual(calls[0], ["/v1/users/me/community/notifications", { muted: true }, { appIntegrityAction: "community:read" }])
    assert.deepEqual(calls[1], ["/v1/users/me/community/topics/7/notifications", { muted: false }, { appIntegrityAction: "community:read" }])
})

test("settings apply after server success and repeated taps cannot issue conflicting saves", async () => {
    const h = harness(), save = deferred()
    await h.render().refresh()
    assert.deepEqual(h.render().notificationSettings, initial)
    h.update(save.promise)
    const pending = h.render().setNotificationsMuted(true)
    assert.equal(h.render().notificationsBusy, true)
    await h.render().setNotificationsMuted(false)
    assert.equal(h.writes.length, 1)
    save.resolve({ muted: true, muted_topic_ids: [7] }); await pending
    assert.deepEqual(h.render().notificationSettings, { muted: true, muted_topic_ids: [7] })
    assert.equal(h.render().notificationsBusy, false)
    h.unmount()
})

test("topic polling started before or during a save cannot undo the saved preference", async () => {
    for (const readFirst of [true, false]) {
        const h = harness(), read = deferred(), save = deferred()
        await h.render().refresh()
        h.topics(read.promise); h.update(save.promise)
        let refresh, update
        if (readFirst) { refresh = h.render().refresh(); await flush(); update = h.render().setNotificationsMuted(true, 7) }
        else { update = h.render().setNotificationsMuted(true, 7); refresh = h.render().refresh(); await flush() }
        save.resolve({ muted: false, muted_topic_ids: [7] }); await update
        read.resolve(response(initial)); await refresh
        assert.deepEqual(h.render().notificationSettings.muted_topic_ids, [7])
        h.unmount()
    }
})

test("failed saving preserves the previous setting and releases controls for a retry", async () => {
    const h = harness()
    await h.render().refresh()
    h.update(Promise.reject(Error("offline")))
    await assert.rejects(h.render().setNotificationsMuted(true), /offline/)
    assert.equal(h.render().notificationsBusy, false)
    assert.deepEqual(h.render().notificationSettings, initial)
    h.update(Promise.resolve({ muted: true, muted_topic_ids: [] }))
    await h.render().setNotificationsMuted(true)
    assert.equal(h.render().notificationSettings.muted, true)
    h.unmount()
})

test("the group switch inverts muted state and topic buttons do not open the topic", () => {
    const jsx = (type, props) => ({ type, props })
    const ui = loadTs("screens/chat/community-notifications.tsx", {
        "react/jsx-runtime": { jsx, jsxs: jsx }, "react-native": { Pressable: "Pressable", View: "View", Text: "Text", Switch: "Switch", StyleSheet: { create: value => value } },
        "react-native-svg": { default: "Svg", Path: "Path" }, "@/providers/language-provider": { useLanguage: () => ({ t: key => key }) }, "@/providers/theme-provider": { useTheme: () => ({ palette: {} }) },
    })
    const values = []
    const row = ui.CommunityGroupNotificationSwitch({ muted: true, busy: false, onChange: value => values.push(value) })
    const toggle = row.props.children.find(node => node.type === "Switch")
    assert.equal(toggle.props.value, false)
    toggle.props.onValueChange(true); assert.deepEqual(values, [false])
    let stopped = 0, clicked = 0
    const button = ui.CommunityNotificationButton({ muted: true, disabled: false, onPress: () => clicked++ })
    assert.equal(button.props.accessibilityLabel, "chat.communityUnmuteTopic")
    button.props.onPress({ stopPropagation: () => stopped++ })
    assert.equal(stopped, 1); assert.equal(clicked, 1)
})
