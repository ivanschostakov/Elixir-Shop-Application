const assert = require("node:assert/strict")
const test = require("node:test")
const load = require("./load-ts.cjs")

test("the discount label distinguishes a partner discount from an entered promo and wallet redemption", () => {
    const { formatAppliedDiscount } = load("utils/discount-display.ts")
    const t = key => ({ "checkout.partnerDiscountTitle": "Партнёрская скидка", "checkout.promoCodeTitle": "Промокод", "checkout.settlementBalanceTitle": "Баланс" })[key]
    assert.equal(formatAppliedDiscount({ source_kind: "app_referral", code: null, discount_percent: "4" }, t), "Партнёрская скидка −4%")
    assert.equal(formatAppliedDiscount({ source_kind: "bitrix_promo", code: "CODE", discount_percent: "3" }, t), "Промокод CODE −3%")
    assert.equal(formatAppliedDiscount({ source_kind: "moysklad_settlement", code: null }, t), "Баланс")
    assert.equal(formatAppliedDiscount({ source_kind: "app_welcome" }, key => key), "checkout.welcomeBonusTitle")
})

const { confirmedBalanceAmount, orderDiscountRows } = load("utils/discount-display.ts")
const order = (settlement) => ({ id: 12, checkout_snapshot: {
    settlement_payment: settlement,
    benefits: { settlement_balance_rubles: "200", bonus_applied_rubles: "10", applications: [
        { source_kind: "app_referral", discount_percent: "10", discount_amount: "100" },
        { source_kind: "app_welcome", discount_amount: "25.50" },
        { source_kind: "moysklad_settlement", discount_amount: "10" },
    ] },
} })

test("only the confirmed invoice difference is shown, never the wallet, estimate or rounded label", () => {
    const confirmed = { status: "confirmed", balance_rubles: "9.87", displayed_spent_rubles: 10 }
    assert.equal(confirmedBalanceAmount(order(confirmed)), 9.87)
    for (const balance_rubles of ["0.00", null, undefined, "-4", "bad"]) {
        assert.equal(confirmedBalanceAmount(order({ ...confirmed, balance_rubles })), null)
    }
    assert.equal(confirmedBalanceAmount(order(undefined)), null)
    assert.deepEqual(orderDiscountRows(order(confirmed).checkout_snapshot).map(row => [row.source_kind, row.amount]),
        [["app_referral", 100], ["app_welcome", 25.5]])
})

test("first QR shows exact kopecks before reopening; no balance row when pending, mismatched or zero", () => {
    const awaiting = order({ status: "awaiting_invoice", gross_rubles: "123.45", maximum_balance_rubles: "10" })
    const qr = { order_id: 12, invoice_id: "inv", awaiting_settlement: false, payment_status: "pending", amount_rubles: 113.58 }
    assert.equal(confirmedBalanceAmount(awaiting, qr), 9.87)
    assert.equal(confirmedBalanceAmount(awaiting), null)
    for (const change of [{ amount_rubles: 123.45 }, { amount_rubles: 124 }, { amount_rubles: 111 },
        { order_id: 13 }, { awaiting_settlement: true }, { invoice_id: null }, { payment_status: "error" }]) {
        assert.equal(confirmedBalanceAmount(awaiting, { ...qr, ...change }), null)
    }
    assert.equal(confirmedBalanceAmount(awaiting, { ...qr, invoice_id: null, payment_method: "later" }), 9.87)
    assert.equal(confirmedBalanceAmount(order({ status: "awaiting_invoice", gross_rubles: "10", maximum_balance_rubles: "10" }),
        { ...qr, invoice_id: null, is_paid: true, amount_rubles: 0 }), 10)
})
