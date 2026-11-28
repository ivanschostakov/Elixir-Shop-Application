const assert = require("node:assert/strict")
const test = require("node:test")
const load = require("./load-ts.cjs")

test("account switch clears personal basket and rejects late previous owner", () => {
    const scope = load("services/commerce-account.ts")
    const store = load("hooks/basket/basket-store.ts", { "@/services/commerce-account": scope, "@/hooks/basket/basket-draft-editing-store": { clearBasketDraftEditingId() {} } })
    scope.setCommerceAccount(1)
    const basket = { user_id: 1, items: [{}], total_quantity: 1, recipient: { name: "A" }, delivery_address: { address: "A" } }
    store.setBasketSnapshot(basket)
    assert.equal(store.getBasketSnapshot(), basket)
    scope.setCommerceAccount(2)
    assert.equal(store.getBasketSnapshot(), null)
    store.setBasketSnapshot(basket)
    assert.equal(store.getBasketSnapshot(), null)
    store.setBasketSnapshot({ ...basket, user_id: 2 })
    store.clearBasketSnapshot()
    assert.equal(store.getBasketSnapshot(), null)
})

test("refund wins over a contradictory paid flag", () => {
    const { resolvePaymentPhase } = load("screens/payment/payment-state.ts")
    assert.equal(resolvePaymentPhase({ is_paid: true, payment_status: "refunded" }, "sbp"), "failure")
})

test("a lost network connection is not reported as an HTTP 503 from the server", async () => {
    let offline = true
    const api = load("services/api/client.ts", {
        "@/services/api/constants": { API_BASE_URL: "https://example.test" },
        "@/services/app-integrity": { AppIntegrityUnavailableError: class extends Error {}, getAppIntegrityHeaders: async () => ({}) },
        "@/services/auth/session": { getAuthTokens: () => null },
        "react-native": { Platform: { OS: "android" } },
        "@/services/api/request-deadline": { ...load("services/api/request-deadline.ts"), RequestDeadlineError: class extends Error {}, fetchTextWithDeadline: async () => {
            if (offline) throw new TypeError("Network request failed")
            return { response: new Response(null, { status: 503 }), text: "" }
        } },
        "@/screens/chat/companion-timezones": { deviceCompanionTimezone: () => "UTC" },
    })
    await assert.rejects(api.apiGet("/catalog"), { status: 0 })
    offline = false
    await assert.rejects(api.apiGet("/catalog"), { status: 503 })
})

test("an account change during device verification prevents sending the previous customer's request", async () => {
    let session = { sessionId: 1, accessToken: "A" }
    let fetched = false
    const api = load("services/api/client.ts", {
        "@/services/api/constants": { API_BASE_URL: "https://example.test" },
        "@/services/app-integrity": { AppIntegrityUnavailableError: class extends Error {},
            getAppIntegrityHeaders: async () => { session = { sessionId: 2, accessToken: "B" }; return {} } },
        "@/services/auth/session": { getAuthTokens: () => session },
        "react-native": { Platform: { OS: "ios" } },
        "@/services/api/request-deadline": { ...load("services/api/request-deadline.ts"), RequestDeadlineError: class extends Error {},
            fetchTextWithDeadline: async () => { fetched = true } },
        "@/screens/chat/companion-timezones": { deviceCompanionTimezone: () => "UTC" },
    })
    await assert.rejects(api.apiGet("/orders"), /Session changed/)
    assert.equal(fetched, false)
})
