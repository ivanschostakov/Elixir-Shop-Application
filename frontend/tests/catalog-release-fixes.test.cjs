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
