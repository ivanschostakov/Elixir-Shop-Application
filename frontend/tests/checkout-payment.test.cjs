const assert = require("node:assert/strict")
const test = require("node:test")
const loadTs = require("./load-ts.cjs")

const constants = loadTs("screens/checkout/checkout-screen.constants.ts")
const {
    buildAvailableRecipients, getProfileRecipientUpdate, getRecipientFormErrors,
    getRecipientPickerValue, getSelfRecipient, hasRecipientErrors,
    resolveRecipientPickerAction, updateSavedRecipientOptions,
} = loadTs("screens/checkout/checkout-screen.utils.ts", {
    "@/screens/checkout/checkout-screen.constants": constants,
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

test("for myself uses current profile and submits only the missing profile fields", () => {
    const profile = { id: 7, name: "Anna", surname: "Tester", phoneNumber: null, email: "anna@example.com" }
    assert.deepEqual(
        getProfileRecipientUpdate(
            { firstName: "Anna", lastName: "Tester", phone: "+7 (913) 537-23-98", email: "anna@example.com" },
            { phone: "required" },
        ),
        { phone_number: "+79135372398" },
    )
    assert.equal(getSelfRecipient(profile).phone, "")
    assert.equal(getSelfRecipient({ ...profile, phoneNumber: "+79135372398" }).phone, "+79135372398")
    assert.deepEqual(
        getProfileRecipientUpdate({ firstName: " Anna ", lastName: "Tester", phone: "", email: " A@EXAMPLE.COM " }, { firstName: "required", email: "required" }),
        { name: "Anna", email: "a@example.com" },
    )
})

test("only real saved selections can enter the recipient selector", () => {
    const saved = { id: 23, name: "Anna" }
    assert.deepEqual(buildAvailableRecipients(null, { recipients: [saved] }), [saved])
    assert.deepEqual(buildAvailableRecipients(saved, { recipients: [saved] }), [saved])
    assert.deepEqual(buildAvailableRecipients({ id: -1 }, { recipients: [saved] }), [saved])
    assert.deepEqual(buildAvailableRecipients(saved, null), [saved])
})

test("the native selector opens add for guests and customers without changing the saved selection", () => {
    const { ADD_NEW_RECIPIENT_VALUE, NO_RECIPIENT_VALUE, SELF_RECIPIENT_VALUE } = constants
    const saved = { id: 23, name: "Anna" }
    assert.equal(getRecipientPickerValue(null, false), NO_RECIPIENT_VALUE)
    assert.equal(getRecipientPickerValue(null, true), SELF_RECIPIENT_VALUE)
    assert.equal(getRecipientPickerValue(saved, true), 23)
    for (const [selected, authenticated] of [[NO_RECIPIENT_VALUE, false], [SELF_RECIPIENT_VALUE, true], [23, true]]) {
        assert.deepEqual(resolveRecipientPickerAction(ADD_NEW_RECIPIENT_VALUE, selected, [saved], authenticated), { type: "add" })
    }
    assert.deepEqual(resolveRecipientPickerAction("23", SELF_RECIPIENT_VALUE, [saved], true), { type: "select", recipient: saved })
    assert.deepEqual(resolveRecipientPickerAction(SELF_RECIPIENT_VALUE, 23, [saved], true), { type: "select", recipient: null })
    assert.equal(resolveRecipientPickerAction("23", 23, [saved], true), null)
})

test("merges the saved server response immediately without an options reload or duplicate", () => {
    const saved = { id: 23, name: "Anna" }
    const prior = { id: 25, name: "Maria" }
    const options = { recipients: [prior, { id: 23, name: "Old name" }], addresses: [{ id: 8 }] }
    const merged = updateSavedRecipientOptions(options, saved)
    assert.deepEqual(merged, { recipients: [saved, prior], addresses: options.addresses })
    assert.equal(getRecipientPickerValue(saved, true), 23)
    assert.equal(updateSavedRecipientOptions(merged, null), merged)
    assert.equal(updateSavedRecipientOptions(merged, { id: -1 }), merged)
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
