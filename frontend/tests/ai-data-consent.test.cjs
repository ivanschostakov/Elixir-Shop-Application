const { test } = require("node:test")
const assert = require("node:assert/strict")
const loadTs = require("./load-ts.cjs")

function setup() {
    let sessionId = 1, granted = false, prompts = 0
    const saved = [], uploads = []
    const api = {
        apiGet: async () => ({ version: "v1", granted }),
        apiPost: async (path, payload) => { saved.push(payload); granted = payload.granted; return { version: "v1", granted } },
        apiPostMultipart: async (...args) => { uploads.push(args); return {} },
    }
    const consent = loadTs("services/api/ai-data-consent.ts", {
        "@/services/api/client": api,
        "@/services/auth/session": { getAuthTokens: () => ({ sessionId }) },
        "@/i18n/translations": { translate: key => key },
    })
    const chat = loadTs("services/api/ai-chat.ts", {
        "@/services/api/client": api,
        "@/services/api/ai-chat.constants": { aiChatEndpoint: "/v1/users/me/ai-chat" },
        "@/services/api/ai-data-consent": consent,
    })
    return { consent, chat, saved, uploads, switchUser: () => { sessionId++ }, setPrompt: fn => consent.registerAiConsentPrompt(async () => { prompts++; return fn() }), prompts: () => prompts }
}

test("declining consent sends neither message nor audio and does not record agreement", async () => {
    const s = setup(); s.setPrompt(() => false)
    await assert.rejects(s.chat.sendMyAiChatMessage("private"), s.consent.AiConsentDeclinedError)
    await assert.rejects(s.chat.transcribeMyAiChatVoice({ uri: "private" }), s.consent.AiConsentDeclinedError)
    assert.equal(s.saved.length, 0); assert.equal(s.uploads.length, 0)
})

test("consent is saved before upload, then not prompted again; revoke prompts again", async () => {
    const s = setup(); s.setPrompt(() => true)
    await s.chat.sendMyAiChatMessage("hello")
    assert.deepEqual(s.saved, [{ granted: true, version: "v1" }])
    assert.equal(s.uploads.length, 1)
    await s.chat.sendMyAiChatMessage("again")
    assert.equal(s.prompts(), 1)
    await s.consent.setAiDataConsent(false, "v1")
    await s.chat.sendMyAiChatMessage("after revoke")
    assert.equal(s.prompts(), 2)
})

test("an account change during the dialog cannot grant consent or send another account's data", async () => {
    const s = setup(); s.setPrompt(() => { s.switchUser(); return true })
    await assert.rejects(s.chat.sendMyAiChatMessage("old account content"), s.consent.AiConsentDeclinedError)
    assert.equal(s.saved.length, 0); assert.equal(s.uploads.length, 0)
})

test("concurrent requests share one consent dialog", async () => {
    const s = setup(); s.setPrompt(() => true)
    await Promise.all([s.consent.ensureAiDataConsent(), s.consent.ensureAiDataConsent()])
    assert.equal(s.prompts(), 1); assert.equal(s.saved.length, 1)
})
