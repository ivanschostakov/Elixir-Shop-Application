const assert = require("node:assert/strict")
const test = require("node:test")
const loadTs = require("./load-ts.cjs")

const constants = loadTs("screens/checkout/checkout-screen.constants.ts")
const {
    buildAvailableRecipients, getProfileRecipientUpdate, getRecipientFormErrors,
    getRecipientPickerValue, getSelfRecipient, hasRecipientErrors,
    recipientPickerLabel, resolveRecipientPickerAction, updateSavedRecipientOptions,
} = loadTs("screens/checkout/checkout-screen.utils.ts", {
    "@/screens/checkout/checkout-screen.constants": constants,
    "@/services/api/delivery": {},
    "@/utils/order-drafts": {},
    "@/utils/formatting": {},
    "@/utils/route-params": {},
    "@/utils/errors": {},
})

test("saved recipients with the same name have distinct labels, even with identical contacts", () => {
    const a = { id: 1, name: "Anna", surname: "Tester", phone: "+70000000001", email: "a@example.com" }
    const b = { ...a, id: 2, phone: "+70000000002", email: "b@example.com" }
    assert.equal(recipientPickerLabel(a, [a]), "Anna Tester")
    assert.match(recipientPickerLabel(a, [a, b]), /000000001$/)
    assert.match(recipientPickerLabel(a, [a, { ...b, phone: a.phone }]), /a@example\.com$/)
    assert.match(recipientPickerLabel(a, [a, { ...a, id: 2 }]), /#1$/)
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

function loadPayments(apiPost, apiGet) {
    return loadTs("services/api/payments.ts", {
        "@/services/api/request-deadline": loadTs("services/api/request-deadline.ts"),
        "@/services/api/client": { apiPost, apiGet, ApiError },
        "@/services/api/constants": { ENDPOINTS: { PAYMENTS: "/payments" } },
    })
}

const pending = () => new ApiError(409, { detail: { code: "settlement_pending" } })

const options = { isActive: () => true, onPending: () => {}, timeoutMessage: "Still preparing" }
const payload = { order_id: 42, payment_method: "sbp" }

test("invoice check and payment creation share two minutes, including manual export retry", async (t) => {
    t.mock.timers.enable({ apis: ["Date"] })
    for (const retryExport of [false, true]) {
        for (const elapsed of [90_000, 120_000]) {
            const posts = []
            const api = loadPayments(async (_, body, opts) => {
                posts.push([body, opts.timeoutMs])
                return { invoice_id: "invoice" }
            }, async (_, __, opts) => {
                assert.equal(opts.timeoutMs, 120_000)
                t.mock.timers.tick(elapsed)
                return { invoice_ready: !retryExport, export_retry_available: retryExport }
            })
            const attempt = api.createPaymentWhenReady(payload, { ...options, checkFirst: true, retryExport })
            if (elapsed === 120_000 || retryExport) await assert.rejects(attempt, api.PaymentPreparationPendingError)
            else assert.equal((await attempt).invoice_id, "invoice")
            const body = retryExport ? { ...payload, retry_export: true } : payload
            assert.deepEqual(posts, elapsed === 120_000 ? [] : [[body, 30_000]])
        }
    }
})

test("pending invoice shows waiting immediately without scheduling a second POST", async (t) => {
    t.mock.timers.enable({ apis: ["setTimeout", "Date"] })
    let posts = 0, waiting = 0
    const api = loadPayments(async () => { posts++; throw pending() })
    await assert.rejects(api.createPaymentWhenReady(payload, { ...options, onPending: () => { waiting++ } }),
        api.PaymentPreparationPendingError)
    t.mock.timers.tick(180_000)
    assert.equal(waiting, 1)
    assert.equal(posts, 1)
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

test("checking a still missing invoice and returning from history only read status (SBP and manager)", async () => {
    for (const method of ["sbp", "later"]) {
        let gets = 0
        const api = loadPayments(() => assert.fail("must not create payment"), async (path, params) => {
            assert.equal(path, "/payments/status")
            assert.deepEqual(params, { order_id: 42, check_invoice: true })
            gets++
            return { payment_status: method === "sbp" ? "draft" : "pending", invoice_ready: false }
        })
        for (let i = 0; i < 2; i++) await assert.rejects(
            api.createPaymentWhenReady({ ...payload, payment_method: method }, { ...options, checkFirst: true }),
            api.PaymentPreparationPendingError)
        assert.equal(gets, 2)
    }
})

test("after a read confirms readiness a single POST uses the same order", async () => {
    const calls = []
    const api = loadPayments(async (path, body) => { calls.push(path); assert.deepEqual(body, payload); return { invoice_id: "invoice" } },
        async path => { calls.push(path); return { payment_status: "draft", invoice_ready: true } })
    assert.equal((await api.createPaymentWhenReady(payload, { ...options, checkFirst: true })).invoice_id, "invoice")
    assert.deepEqual(calls, ["/payments/status", "/payments/create"])
})

test("already paid, existing QR, canceled, and completed manager orders never start payment again", async () => {
    for (const state of [{ is_paid: true }, { invoice_id: "qr" }, { payment_status: "canceled" },
        { payment_status: "refunded" }, { payment_status: "pending", payment_method: "later" }]) {
        const api = loadPayments(() => assert.fail("duplicate"), async () => state)
        assert.equal(await api.createPaymentWhenReady(payload, { ...options, checkFirst: true }), state)
    }
})

test("a late readiness response after leaving checkout cannot start payment", async () => {
    let active = true
    const api = loadPayments(() => assert.fail("stale request"), async () => { active = false; return { invoice_ready: true } })
    assert.equal(await api.createPaymentWhenReady(payload, { ...options, checkFirst: true, isActive: () => active }), null)
})

const { mergePaymentState, resolvePaymentPhase } = loadTs("screens/payment/payment-state.ts")

test("only an explicit retry resumes the same exhausted export", async () => {
    const posts = []
    const api = loadPayments(async (_, body) => { posts.push(body); throw pending() },
        async () => ({ payment_status: "draft", invoice_ready: false, export_retry_available: true }))
    for (const retryExport of [false, true]) {
        await assert.rejects(api.createPaymentWhenReady(payload, { ...options, checkFirst: true, retryExport }),
            api.PaymentPreparationPendingError)
    }
    assert.deepEqual(posts, [{ ...payload, retry_export: true }])
    assert.equal(resolvePaymentPhase({ payment_status: "draft", payment_method: "later" }, "later"), "waiting")
    assert.equal(resolvePaymentPhase({ payment_status: "pending", invoice_ready: false }, "later"), "waiting")
})

test("a pending or late QR keeps SBP open while offline payment still closes checkout", () => {
    const pendingSbp = { order_id: 42, invoice_id: "first", payment_method: "sbp", payment_status: "pending",
        is_paid: false, qr_url: null, qr_image: null, expires_at: null }
    assert.equal(resolvePaymentPhase(pendingSbp, "sbp"), "sbp")
    assert.equal(resolvePaymentPhase({ ...pendingSbp, payment_method: "later" }, "sbp"), "pending")
    const qr = mergePaymentState(pendingSbp, { ...pendingSbp, qr_url: "https://example.test/pay" })
    assert.equal(resolvePaymentPhase(qr, "sbp"), "sbp")
    assert.equal(qr.qr_url, "https://example.test/pay")
    assert.equal(mergePaymentState(qr, pendingSbp).qr_url, qr.qr_url)
    assert.equal(mergePaymentState(qr, { ...pendingSbp, invoice_id: "second" }).qr_url, null)
    assert.equal(resolvePaymentPhase({ ...pendingSbp, is_paid: true }, "sbp"), "success")
    assert.equal(resolvePaymentPhase({ ...pendingSbp, payment_status: "canceled" }, "sbp"), "failure")
})
