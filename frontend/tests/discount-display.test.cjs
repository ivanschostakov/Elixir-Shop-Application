const assert = require("node:assert/strict")
const test = require("node:test")
const load = require("./load-ts.cjs")

test("the discount label distinguishes a partner discount from an entered promo and wallet redemption", () => {
    const { formatAppliedDiscount } = load("utils/discount-display.ts")
    const t = key => ({ "checkout.partnerDiscountTitle": "Партнёрская скидка", "checkout.promoCodeTitle": "Промокод", "checkout.bonusRublesTitle": "Баланс" })[key]
    assert.equal(formatAppliedDiscount({ source_kind: "app_referral", code: null, discount_percent: "4" }, t), "Партнёрская скидка −4%")
    assert.equal(formatAppliedDiscount({ source_kind: "bitrix_promo", code: "CODE", discount_percent: "3" }, t), "Промокод CODE −3%")
    assert.equal(formatAppliedDiscount({ source_kind: "moysklad_settlement", code: null }, t), "Баланс")
})
