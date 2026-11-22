const assert = require("node:assert/strict")
const test = require("node:test")
const load = require("./load-ts.cjs")

test("cart item prices use the server merchandise quote, without allocating the wallet to items", () => {
    const { getQuotedItemPrice } = load("utils/quoted-item-price.ts")
    const item = { variant_id: 126, quantity: 3, unit_price: "2990.00", original_unit_price: "2990.00", line_total: "8970.00", discount_percent: "0" }
    const quote = { priced_items: [{ variant_id: 126, quantity: 3, unit_price: "2481.70", line_total: "7445.10" }], bonus_applied_rubles: "1000" }
    const displayed = getQuotedItemPrice(item, quote)
    assert.equal(displayed.unit_price, "2481.70")
    assert.equal(displayed.line_total, "7445.10")
    assert.equal(displayed.original_unit_price, "2990.00")
    assert.equal(displayed.discount_percent, "17")
    assert.equal(item.line_total, "8970.00")
    assert.equal(getQuotedItemPrice(item, null), item)
    assert.equal(getQuotedItemPrice({ ...item, quantity: 2 }, quote).unit_price, "2990.00")
    for (const line of [
        { unit_price: "2481.70", line_total: "6445.10" },
        { unit_price: "3000", line_total: "9000" },
        { unit_price: "NaN", line_total: "NaN" },
    ]) assert.equal(getQuotedItemPrice(item, { priced_items: [{ ...quote.priced_items[0], ...line }] }), item)
})
