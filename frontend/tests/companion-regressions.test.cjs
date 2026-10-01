const { test } = require("node:test")
const assert = require("node:assert/strict")
const loadTs = require("./load-ts.cjs")

test("first save asks once; opening chat never grants consent and cancellation saves nothing", async () => {
    const { withStorageConsent, CompanionActionCancelled } = loadTs("screens/chat/companion-consent.ts")
    const state = { consent_required: true, consent_version: "companion-v1" }
    const action = { kind: "confirm", message_id: 42, action_id: "card", action_token: "token" }
    let prompts = 0
    await assert.rejects(withStorageConsent(state, action, async () => { prompts++; return false }), CompanionActionCancelled)
    const approved = await withStorageConsent(state, action, async version => { prompts++; assert.equal(version, "companion-v1"); return true })
    assert.deepEqual(approved, { ...action, adult_confirmed: true, consent_version: "companion-v1" })
    assert.equal(action.adult_confirmed, undefined)
    assert.equal(await withStorageConsent({ ...state, consent_required: false }, action, async () => { throw Error("must not prompt") }), action)
    for (const kind of ["disable", "cancel", "delete_entry"]) {
        assert.deepEqual(await withStorageConsent(state, { kind }, async () => { throw Error("must not prompt") }), { kind })
    }
    assert.equal(prompts, 2)
})

test("companion OTA handles an older backend without masking authentication or server errors", async () => {
    class ApiError extends Error { constructor(status) { super(String(status)); this.status = status } }
    let failure = new ApiError(404)
    const api = loadTs("services/api/companion.ts", {
        "@/services/api/client": { ApiError, apiGet: async () => { throw failure } },
        "@/services/api/ai-chat.constants": { aiChatEndpoint: "/v1/users/me/ai-chat" },
    })
    assert.deepEqual(await api.getCompanionAvailability(), { available: false, consent_version: "" })
    for (const status of [401, 403, 500]) {
        failure = new ApiError(status)
        await assert.rejects(api.getCompanionAvailability(), error => error === failure)
    }
})

test("companion API actions have stable explicit keys and verified native action", async () => {
    const requests = []
    const api = loadTs("services/api/companion.ts", {
        "@/services/api/client": { apiPost: async (...args) => requests.push(args), apiGet: async (...args) => requests.push(args), apiDelete: async (...args) => requests.push(args) },
        "@/services/api/ai-chat.constants": { aiChatEndpoint: "/v1/users/me/ai-chat" },
    })
    await api.actCompanion({ kind: "event", resource_id: 123, expected_version: 4, request_key: "same-key-123", status: "done" })
    await api.actCompanion({ kind: "event", resource_id: 123, expected_version: 4, request_key: "same-key-123", status: "done" })
    assert.equal(requests[0][0], "/v1/users/me/ai-chat/companion/actions")
    assert.equal(requests[0][1].request_key, requests[1][1].request_key)
    assert.equal(requests[0][2].appIntegrityAction, "ai-companion")
    await api.eraseCompanion()
    assert.equal(requests[2][0], "/v1/users/me/ai-chat/companion?confirm=true")
})

test("ordinary and companion chat use separate routes without changing the original call", async () => {
    const requests = []
    const api = loadTs("services/api/ai-chat.ts", {
        "@/services/api/client": { apiPostMultipart: async (...args) => requests.push(args) },
        "@/services/api/ai-chat.constants": { aiChatEndpoint: "/v1/users/me/ai-chat" },
        "@/services/api/ai-data-consent": { ensureAiDataConsent: async () => undefined },
    })
    await api.sendMyAiChatMessage("ordinary", [])
    await api.sendMyAiChatMessage("companion", [], "message-request-001")
    assert.equal(requests[0][0], "/v1/users/me/ai-chat")
    assert.equal(requests[0][2].appIntegrityAction, "ai-chat:send")
    assert.equal(requests[0][1].get("chat_mode"), null)
    assert.equal(requests[1][0], "/v1/users/me/ai-chat/companion/messages")
    assert.equal(requests[1][1].get("client_request_id"), "message-request-001")
    assert.equal(requests[1][2].appIntegrityAction, "ai-companion")
})

test("explicit ordinary chat sends the mode flag while mentor requests retain protocol 2", async () => {
    const requests = []
    let consentChecks = 0
    const api = loadTs("services/api/ai-chat.ts", {
        "@/services/api/client": { apiPostMultipart: async (...args) => requests.push(args) },
        "@/services/api/ai-chat.constants": { aiChatEndpoint: "/v1/users/me/ai-chat" },
        "@/services/api/ai-data-consent": { ensureAiDataConsent: async () => { consentChecks++ } },
    })
    await api.sendMyAiChatMessage("ordinary", [], undefined, 2, true)
    await api.sendMyAiChatMessage("mentor", [], "mentor-request-001", 2)
    assert.equal(consentChecks, 2)
    assert.equal(requests[0][0], "/v1/users/me/ai-chat")
    assert.equal(requests[0][1].get("chat_mode"), "ordinary")
    assert.equal(requests[0][1].get("dialogue_protocol"), null)
    assert.equal(requests[0][1].get("client_request_id"), null)
    assert.equal(requests[0][2].appIntegrityAction, "ai-chat:send")
    assert.equal(requests[1][0], "/v1/users/me/ai-chat/companion/messages")
    assert.equal(requests[1][1].get("chat_mode"), null)
    assert.equal(requests[1][1].get("dialogue_protocol"), "2")
    assert.equal(requests[1][1].get("client_request_id"), "mentor-request-001")
    assert.equal(requests[1][2].appIntegrityAction, "ai-companion")
})

test("chat sends follow the resolved mentor mode without changing the saved profile", async () => {
    const requests = []
    const profile = { enabled: true, version: 4 }
    let mentorShown = true
    const { useAiChat } = loadTs("hooks/chat/use-ai-chat.ts", {
        react: {
            useEffect: () => {},
            useRef: current => ({ current }),
            useState: initial => [initial, () => {}],
        },
        "@react-navigation/native": { useIsFocused: () => true },
        "@/hooks/basket/basket-store": { setBasketSnapshot: () => {} },
        "@/hooks/shared/use-async-data": { useAsyncData: () => ({ data: null, error: null, loading: false, reload: async () => null, setData: () => {} }) },
        "@/services/api/ai-chat": { sendMyAiChatMessage: async (...args) => { requests.push(args); return { chat: { messages: [] } } } },
        "@/services/api/companion": { requestKey: () => "mentor-request-001" },
        "@/services/api/ai-data-consent": { AiConsentDeclinedError: class extends Error {} },
    })
    const chat = useAiChat(async () => mentorShown && profile.enabled, () => 2)
    await chat.sendMessage("mentor")
    mentorShown = false
    await chat.sendMessage("ordinary")
    mentorShown = true
    await chat.sendMessage("mentor again")
    assert.deepEqual(requests, [
        ["mentor", [], "mentor-request-001", 2, false],
        ["ordinary", [], undefined, 2, true],
        ["mentor again", [], "mentor-request-001", 2, false],
    ])
    assert.deepEqual(profile, { enabled: true, version: 4 })
})

test("failed chat retries retain their key only while the resolved mode stays the same", async () => {
    const requests = []
    let mentorShown = true
    let keyIndex = 0
    const { useAiChat } = loadTs("hooks/chat/use-ai-chat.ts", {
        react: {
            useEffect: () => {},
            useRef: current => ({ current }),
            useState: initial => [initial, () => {}],
        },
        "@react-navigation/native": { useIsFocused: () => true },
        "@/hooks/basket/basket-store": { setBasketSnapshot: () => {} },
        "@/hooks/shared/use-async-data": { useAsyncData: () => ({ data: null, error: null, loading: false, reload: async () => null, setData: () => {} }) },
        "@/services/api/ai-chat": { sendMyAiChatMessage: async (...args) => { requests.push(args); throw new Error("offline") } },
        "@/services/api/companion": { requestKey: () => `retry-key-${++keyIndex}` },
        "@/services/api/ai-data-consent": { AiConsentDeclinedError: class extends Error {} },
    })
    const chat = useAiChat(async () => mentorShown, () => 2)
    await assert.rejects(chat.sendMessage("same draft"), /offline/)
    await assert.rejects(chat.sendMessage("same draft"), /offline/)
    mentorShown = false
    await assert.rejects(chat.sendMessage("same draft"), /offline/)
    mentorShown = true
    await assert.rejects(chat.sendMessage("same draft"), /offline/)
    assert.deepEqual(requests.map(args => args[2]), ["retry-key-1", "retry-key-1", undefined, "retry-key-3"])
    assert.deepEqual(requests.map(args => args[4]), [false, false, true, false])
    assert.equal(keyIndex, 3)
})

test("private diary attachments never resolve to public media URLs", () => {
    const { getReadAttachmentUri } = loadTs("screens/chat/chat-attachments.ts", {
        "react-native": { Platform: { OS: "ios" } },
        "expo-image-picker": {},
        "@/services/api/constants": { API_BASE_URL: "https://example.test/api" },
        "@/screens/chat/chat-screen.constants": { DIRECT_ATTACHMENT_URI_PATTERN: /^(https?:|file:)/, CHAT_IMAGE_ATTACHMENT_EXTENSIONS: new Set() },
    })
    const uri = getReadAttachmentUri({ id: 7, is_private: true, relative_path: "12/secret.jpg", download_path: "/api/v1/users/me/ai-chat/attachments/7" })
    assert.equal(uri, "https://example.test/api/v1/users/me/ai-chat/attachments/7")
    assert.ok(!uri.includes("/media/"))
})
