import type { BenefitCheckResponse } from "@/services/api/benefits.types"

type ItemPrice = {
    variant_id: number
    quantity: number
    unit_price: string
    line_total: string
    original_unit_price?: string | null
    discount_percent?: string
}

/** Item quotes contain merchandise discounts; balance redemption stays in the order total. */
export function getQuotedItemPrice<T extends ItemPrice>(item: T, benefits: BenefitCheckResponse | null): T {
    const quote = benefits?.priced_items?.find(line => line.variant_id === item.variant_id && line.quantity === item.quantity)
    if (!quote) return item
    const unit = Number(quote.unit_price)
    const line = Number(quote.line_total)
    const original = Number(item.original_unit_price ?? item.unit_price)
    if (!Number.isFinite(unit) || !Number.isFinite(line) || !Number.isFinite(original)
        || unit < 0 || unit > Number(item.unit_price) || Math.round(unit * item.quantity * 100) !== Math.round(line * 100)) return item
    return {
        ...item,
        unit_price: quote.unit_price,
        line_total: quote.line_total,
        original_unit_price: item.original_unit_price ?? item.unit_price,
        discount_percent: original > 0 ? String(Math.round((1 - unit / original) * 10000) / 100) : "0",
    }
}
