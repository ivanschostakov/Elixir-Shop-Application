const assert = require("node:assert/strict")
const test = require("node:test")
const loadTs = require("./load-ts.cjs")

const { getRecipientFormErrors, hasRecipientErrors } = loadTs("screens/checkout/checkout-screen.utils.ts", {
    "@/services/api/delivery": {},
    "@/utils/order-drafts": {},
    "@/utils/formatting": {},
    "@/utils/route-params": {},
    "@/utils/errors": {},
})

test("checks all required fields of the selected recipient", () => {
    const valid = { firstName: "Anna", lastName: "Tester", phone: "+7 (913) 537-23-98", email: "anna@example.com" }
    const t = (key) => key
    assert.equal(hasRecipientErrors(getRecipientFormErrors(valid, t)), false)
    for (const field of Object.keys(valid)) {
        assert.ok(getRecipientFormErrors({ ...valid, [field]: " " }, t)[field])
    }
    assert.equal(getRecipientFormErrors({ ...valid, email: "invalid" }, t).email, "checkout.recipientEmailInvalid")
})

class ApiError extends Error {
    constructor(status, body) {
        super("API error")
        this.status = status
        this.body = body
    }
}

function loadPayments(apiPost) {
    return loadTs("services/api/payments.ts", {
        "@/services/api/client": { apiPost, ApiError },
        "@/services/api/constants": { ENDPOINTS: { PAYMENTS: "/payments" } },
    })
}

const pending = () => new ApiError(409, { detail: { code: "settlement_pending" } })

test("retries pending settlement for the same order", async (t) => {
    t.mock.timers.enable({ apis: ["setTimeout"] })
    const payload = { order_id: 42, payment_method: "sbp" }
    const calls = []
    const { createPaymentWhenReady } = loadPayments(async (_path, body) => {
        calls.push(body)
        if (calls.length === 1) throw pending()
        return { order_id: 42, invoice_id: "invoice" }
    })
    let waiting = 0
    const result = createPaymentWhenReady(payload, {
        isActive: () => true,
        onPending: () => { waiting++ },
        timeoutMessage: "not ready",
    })
    await Promise.resolve()
    t.mock.timers.tick(4_000)
    assert.deepEqual(await result, { order_id: 42, invoice_id: "invoice" })
    assert.deepEqual(calls, [payload, payload])
    assert.equal(waiting, 1)
})

test("does not retry mismatches or ambiguous gateway errors", async () => {
    for (const error of [new ApiError(409, { detail: "invoice mismatch" }), new ApiError(503, null)]) {
        let calls = 0
        const { createPaymentWhenReady } = loadPayments(async () => { calls++; throw error })
        await assert.rejects(createPaymentWhenReady({ order_id: 42 }, {
            isActive: () => true, onPending: () => assert.fail("unexpected retry"), timeoutMessage: "not ready",
        }), (actual) => actual === error)
        assert.equal(calls, 1)
    }
})
