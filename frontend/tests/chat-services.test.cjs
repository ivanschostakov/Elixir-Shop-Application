const assert = require("node:assert/strict")
const test = require("node:test")
const loadTs = require("./load-ts.cjs")

test("support requests retain integrity and attachments and never call AI endpoints", async () => {
    const calls = []
    class FormData {
        fields = []
        append(...args) { this.fields.push(args) }
    }
    const originalFormData = global.FormData
    global.FormData = FormData
    try {
        const api = loadTs("services/api/support.ts", {
            "@/services/api/constants": { ENDPOINTS: { USERS: "/v1/users" } },
            "@/services/api/client": Object.fromEntries(["apiGet", "apiPost", "apiPostMultipart"].map(method => [method, (...args) => { calls.push({ method, args }); return Promise.resolve({ id: 12 }) }])),
        })
        await api.getMySupportInbox()
        await api.getMySupportConversation(12)
        await api.createMySupportConversation({ client_message_id: "first", message: "Order question" })
        await api.sendMySupportMessage(12, { clientMessageId: "next", message: "Photo", attachments: [{ uri: "file:///photo.jpg", mimeType: "image/jpeg", fileName: "photo.jpg" }] })
        await api.markMySupportConversationRead(12)
        await api.downloadSupportAttachment(42)
        assert.equal(calls.length, 6)
        assert.equal(calls[5].args[0], "/v1/users/me/support/attachments/42")
        assert.equal(calls[5].args[2].responseType, "blob")
        for (const { args } of calls) {
            assert.ok(args[0].startsWith("/v1/users/me/support"))
            assert.match(args[2].appIntegrityAction, /^support:(read|write)$/)
        }
        assert.deepEqual(calls[3].args[1].fields, [["client_message_id", "next"], ["message", "Photo"], ["attachments", { uri: "file:///photo.jpg", name: "photo.jpg", type: "image/jpeg" }]])
    } finally {
        global.FormData = originalFormData
    }
})

test("notifications open the restored AI, Mentor, Community and support destinations", async () => {
    let onResponse
    let unsubscribed = false
    const navigations = []
    const notifications = loadTs("services/notifications/order-status-notifications.ts", {
        "expo-constants": { default: {} },
        "expo-notifications": {
            addNotificationResponseReceivedListener: callback => { onResponse = callback; return { remove: () => { unsubscribed = true } } },
            getLastNotificationResponseAsync: async () => null,
        },
        "expo-router": {},
        "react-native": { Platform: { OS: "ios" } },
        "@/constants/routes": { ROUTES: { chat: "/chat", payment: "/payment", profileHistory: "/profile-history", discover: "/discover", basket: "/basket" }, getProductRoute: id => `/products/${id}` },
        "@/services/api/users": {},
    })
    const dispose = notifications.attachPushOpenListener(target => navigations.push(target))
    let id = 0
    const deliver = data => onResponse({ notification: { request: { identifier: String(++id), content: { data } } } })
    for (const type of ["ai_reply", "ai_companion", "ai_companion_supply", "community_message"]) deliver({ type, topic_id: 5 })
    assert.deepEqual(navigations.splice(0), [
        { pathname: "/chat", params: { mode: "ai" } },
        { pathname: "/chat", params: { mode: "ai", companion: "1" } },
        { pathname: "/chat", params: { mode: "ai", companion: "1" } },
        { pathname: "/chat", params: { mode: "community", topicId: "5" } },
    ])
    deliver({ type: "support_reply", conversation_id: 12 })
    assert.deepEqual(navigations.pop(), { pathname: "/chat", params: { mode: "support", conversationId: "12" } })
    deliver({ type: "abandoned_cart" })
    assert.equal(navigations.pop(), "/basket")
    dispose()
    assert.equal(unsubscribed, true)
    deliver({ type: "support_reply", conversation_id: 12 })
    assert.deepEqual(navigations, [])
})

test("a mentor native action opens its private notice once across cold and live callbacks", async () => {
    const response = { notification: { request: { identifier: "native-1", content: { data: {
        type: "ai_companion", mentor_notice: true, key: "water:2030-01-10", profile: 4,
    } } } }, actionIdentifier: "water" }
    let live, cleared = 0
    const routes = []
    const service = loadTs("services/notifications/order-status-notifications.ts", {
        "expo-constants": { default: {} }, "expo-notifications": {
            DEFAULT_ACTION_IDENTIFIER: "default",
            getLastNotificationResponseAsync: async () => response,
            clearLastNotificationResponseAsync: async () => { cleared++ },
            addNotificationResponseReceivedListener(cb) { live = cb; return { remove() {} } },
        },
        "react-native": { Platform: { OS: "ios" } }, "@/constants/routes": {}, "@/services/api/users": {},
    })
    const detach = service.attachPushOpenListener(route => routes.push(route))
    live(response)
    await new Promise(resolve => setImmediate(resolve))
    assert.deepEqual(routes, [{ pathname: "/mentor-notice", params: { profile: "4", notice: "water:2030-01-10", action: "water" } }])
    assert.equal(cleared, 1)
    detach()
})

test("native rest and empty prompts follow the actual workout and respect opt-outs and logout", async t => {
    const at = Date.parse("2030-01-10T13:00:00Z")
    let now = at
    t.mock.method(Date, "now", () => now)
    const pending = new Map(), scheduled = [], storage = new Map(), categories = new Map()
    const app = { currentState: "active", addEventListener(_, cb) { this.changed = cb } }
    const module = loadTs("services/notifications/mentor-push.ts", {
        "react-native": { Platform: { OS: "ios" }, AppState: app },
        "expo-secure-store": {
            getItemAsync: async key => storage.get(key) ?? null,
            setItemAsync: async (key, value) => storage.set(key, value), deleteItemAsync: async key => storage.delete(key),
        },
        "expo-notifications": {
            SchedulableTriggerInputTypes: { DATE: "date" },
            getAllScheduledNotificationsAsync: async () => [...pending.values()],
            scheduleNotificationAsync: async n => { scheduled.push(n); pending.set(n.identifier, n) },
            cancelScheduledNotificationAsync: async key => pending.delete(key),
            setNotificationCategoryAsync: async (key, actions) => categories.set(key, actions),
        },
    })
    await module.registerMentorCategories()
    assert.deepEqual(categories.get("mentor_continue_extend").map(a => a.identifier), ["continue", "extend"])
    const r = { id: 8, version: 1, occurred_at: new Date(at).toISOString(), data: { workout: {
        status: "in_progress", current_exercise_index: 0, exercises: [{ name: "Тяга", sets: [{ completed: false }] }],
    } } }
    const state = { profile: { id: 4, enabled: true, settings: { mobile: { topics: ["rest", "unfinished"] } } }, open_workouts: [r] }
    await module.syncMentorSessionTimers(state)
    assert.equal(scheduled.length, 0)
    const background = async value => { app.currentState = value; app.changed(value); await module.syncMentorSessionTimers(state) }
    await background("background")
    assert.equal(scheduled.at(-1).content.data.kind, "empty")
    await background("active")
    assert.equal(pending.size, 0)
    await background("background")
    now += 11 * 60_000
    pending.clear() // The OS delivered it during suspension.
    await background("active")
    const count = scheduled.length
    await background("background")
    assert.equal(scheduled.length, count)
    r.version++
    r.data.workout.exercises[0].sets[0].completed = true
    r.data.workout.rest_ends_at = new Date(now + 30000).toISOString()
    await module.syncMentorSessionTimers(state)
    assert.equal(scheduled.at(-1).content.data.kind, "rest")
    await module.syncMentorSessionTimers(state)
    assert.equal(scheduled.length, count + 1)
    state.profile.settings.mobile.topics = []
    await module.syncMentorSessionTimers(state)
    assert.equal(pending.size, 0)
    state.profile.settings.mobile.topics = ["rest"]
    await module.syncMentorSessionTimers(state)
    assert.equal(pending.size, 1)
    await module.syncMentorSessionTimers(null)
    assert.equal(pending.size, 0)
})
