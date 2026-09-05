const { test } = require("node:test")
const assert = require("node:assert/strict")
const { readFileSync } = require("node:fs")
const { join } = require("node:path")
const loadTs = require("./load-ts.cjs")

test("dialogue v2 is negotiated explicitly; ordinary chat remains unchanged", async () => {
    const requests = []
    const api = loadTs("services/api/ai-chat.ts", {
        "@/services/api/client": { apiPostMultipart: async (...args) => requests.push(args) },
        "@/services/api/ai-chat.constants": { aiChatEndpoint: "/ai-chat" },
    })
    await api.sendMyAiChatMessage("вес 84", [], "request-key-1", 2)
    await api.sendMyAiChatMessage("обычный чат")
    assert.equal(requests[0][1].get("dialogue_protocol"), "2")
    assert.equal(requests[0][2].appIntegrityAction, "ai-companion")
    assert.equal(requests[1][1].get("dialogue_protocol"), null)
})

test("quick reports and introductions use the authenticated server, not a model", async () => {
    const requests = []
    const api = loadTs("services/api/companion.ts", {
        "@/services/api/client": { apiPost: async (...args) => requests.push(args) },
        "@/services/api/ai-chat.constants": { aiChatEndpoint: "/ai-chat" },
    })
    await api.companionDialogue("progress", 30, "stable-report-key")
    assert.deepEqual(requests[0], ["/ai-chat/companion/dialogue", { kind: "progress", days: 30, request_key: "stable-report-key" }, { appIntegrityAction: "ai-companion" }])
})

test("discarding/editing a draft never grants consent; confirming does", async () => {
    const { withStorageConsent } = loadTs("screens/chat/companion-consent.ts")
    const state = { consent_required: true, consent_version: "test" }
    for (const kind of ["dialogue_cancel", "dialogue_edit"]) {
        const result = await withStorageConsent(state, { kind }, () => { throw new Error("No consent required") })
        assert.deepEqual(result, { kind })
    }
    const saved = await withStorageConsent(state, { kind: "dialogue_confirm" }, async () => true)
    assert.equal(saved.adult_confirmed, true)
    assert.equal(saved.consent_version, "test")
})

test("new companion controls stay in chat and reuse operation keys on retry", () => {
    const source = readFileSync(join(__dirname, "../screens/chat/companion-dialogue.tsx"), "utf8")
    assert.ok(!source.includes("<Modal") && !source.includes("TextInput"))
    assert.ok(source.includes('testID="companion-dialogue-panel"'))
    assert.ok(source.includes("keys.current.get(identity) ?? requestKey()"))
    assert.ok(source.includes('perform(card, "dialogue_edit")'))
    assert.ok(source.includes('perform(card, "dialogue_undo")'))
    assert.ok(source.includes("formatCompanionDate(i.occurred_at, clock)"))
    assert.ok(source.includes("i.local_date"))
    assert.ok(source.includes('backgroundColor: "transparent"'))
    assert.ok(source.includes("CoursePlanDetails"))
    assert.ok(source.includes("dateRange(stage.start_date, stage.end_date)"))
    assert.ok(source.includes('tone="primary"'))
})

test("AI-recommended courses are visibly distinguished from user-supplied plans", () => {
    const api = readFileSync(join(__dirname, "../services/api/companion.ts"), "utf8")
    const dialogue = readFileSync(join(__dirname, "../screens/chat/companion-dialogue.tsx"), "utf8")
    assert.match(api, /"ai_recommended_plan"/)
    assert.match(dialogue, /Рекомендация ИИ, а не медицинское назначение/)
})
