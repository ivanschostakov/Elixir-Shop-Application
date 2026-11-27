const { test } = require("node:test")
const assert = require("node:assert/strict")
const loadTs = require("./load-ts.cjs")

const html = loadTs("components/content/html-content.utils.ts", {
    "@/components/content/html-content.const": { HTML_TAG_PATTERN: /<\/?[a-z][\s\S]*>/i },
})
const { getPlainTextContent } = loadTs("components/content/product-content.ts", {
    "@/components/content/html-content.utils": html,
})
const { formatAppliedDiscount } = loadTs("utils/discount-display.ts")

test("FAQ script artifacts are removed from rich text and product subtitles", () => {
    const faq = "(function () { var items = document.querySelectorAll('details'); items.forEach(function (item) { item.open = true; }); })();"
    const value = `<h3>FAQ</h3>${faq}&lt;script&gt;broken&lt;/script&gt;<p>Visible text</p>`
    assert.equal(html.normalizeHtml(value), "<div><h3>FAQ</h3><p>Visible text</p></div>")
    assert.equal(getPlainTextContent(value), "FAQ Visible text")
    assert.equal(html.hasRenderableHtmlContent(faq), false)
})

test("the promo name and actual percent are shown without calling a balance payment a promo", () => {
    const t = key => ({
        "checkout.promoCodeTitle": "Промокод",
        "checkout.bonusRublesTitle": "Бонусные рубли",
        "checkout.estimatedBalance": "С баланса автоматически (предварительно)",
        "checkout.discountTitle": "Скидка",
    })[key]
    assert.equal(formatAppliedDiscount({ source_kind: "bitrix_promo", code: "ROMANI", discount_percent: "3.00" }, t), "Промокод ROMANI −3%")
    assert.equal(formatAppliedDiscount({ source_kind: "bitrix_promo", code: "SALE", discount_percent: null }, t), "Промокод SALE")
    assert.equal(formatAppliedDiscount({ source_kind: "moysklad_settlement", discount_percent: null }, t, "automatic"), "С баланса автоматически (предварительно)")
    assert.equal(formatAppliedDiscount({ source_kind: "moysklad_bonus" }, t), "Бонусные рубли")
})
