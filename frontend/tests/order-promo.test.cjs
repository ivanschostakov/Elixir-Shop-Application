const assert = require("node:assert/strict")
const test = require("node:test")
const { hasAppliedOrderPromo } = require("./load-ts.cjs")("screens/cart/order-promo.ts")

test("only the actual rounded discount for the selected code confirms it", () => {
    const promo = {code: "хрюн_слим", is_applicable: true, applied_discount_amount: "30.00"}
    const welcome = {code: null, is_applicable: true, applied_discount_amount: "500.00"}
    const quote = {stacked_discount_options: [promo, welcome]}
    assert.equal(hasAppliedOrderPromo(quote, "ХРЮН_СЛИМ"), true)
    assert.equal(hasAppliedOrderPromo(quote, "other"), false)
    assert.equal(hasAppliedOrderPromo({...quote, unresolved_code_reason: "invalid"}, promo.code), false)
    assert.equal(hasAppliedOrderPromo({stacked_discount_options: [welcome, {...promo, applied_discount_amount: "0"}]}, promo.code), false)
})
