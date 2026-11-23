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
        assert.equal(calls.length, 5)
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
