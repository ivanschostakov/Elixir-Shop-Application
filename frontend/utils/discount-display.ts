import type { TranslationKey } from "@/i18n/translations"
import type { BenefitCheckResponse, BenefitOptionResponse } from "@/services/api/benefits.types"
import type { OrderRead } from "@/services/api/orders.types"
import type { PaymentStatusRead } from "@/services/api/payments.types"

type Discount = Pick<BenefitOptionResponse, "source_kind" | "code" | "discount_percent">

export function formatAppliedDiscount(option: Discount, t: (key: TranslationKey) => string, mode?: BenefitCheckResponse["balance_redemption_mode"]) {
    if (option.source_kind === "app_welcome") return t("checkout.welcomeBonusTitle")
    if (option.source_kind === "moysklad_settlement") return t(mode === "automatic" ? "checkout.estimatedBalance" : "checkout.settlementBalanceTitle")
    const isBalance = option.source_kind === "moysklad_bonus"
    const isPartner = option.source_kind === "app_referral"
    const isPromo = !isBalance && !isPartner && Boolean(option.code || option.source_kind === "bitrix_promo")
    const label = t(isPartner ? "checkout.partnerDiscountTitle" : isPromo ? "checkout.promoCodeTitle" : isBalance ? "checkout.bonusRublesTitle" : "checkout.discountTitle")
    const percent = Number(option.discount_percent)
    const code = isPromo && option.code ? ` ${option.code}` : ""
    return `${label}${code}${!isBalance && percent > 0 ? ` −${String(percent).replace(".", ",")}%` : ""}`
}

function record(value: unknown): Record<string, unknown> | undefined {
    if (value && typeof value === "object" && !Array.isArray(value)) return value as Record<string, unknown>
}

function minorUnits(value: unknown) {
    if ((typeof value !== "string" && typeof value !== "number") || !/^\d+(\.\d{1,2})?$/.test(String(value))) return null
    const cents = Math.round(Number(value) * 100)
    return Number.isSafeInteger(cents) ? cents : null
}

export function confirmedBalanceAmount(order?: Pick<OrderRead, "id" | "checkout_snapshot"> | null, payment?: PaymentStatusRead | null) {
    const settlement = record(order?.checkout_snapshot?.settlement_payment)
    if (!order || !settlement) return null
    let cents: number | null = null
    if (settlement.status === "confirmed") {
        cents = minorUnits(settlement.balance_rubles)
    } else if (settlement.status === "awaiting_invoice" && payment?.order_id === order.id
        && payment.awaiting_settlement === false
        && (payment.is_paid || (payment.invoice_id && ["created", "pending"].includes(payment.payment_status ?? ""))
            || (payment.payment_method === "later" && payment.payment_status === "pending"))) {
        // The initial order snapshot can predate the invoice returned by the payment endpoint.
        const gross = minorUnits(settlement.gross_rubles)
        const cash = minorUnits(payment.amount_rubles)
        const maximum = minorUnits(settlement.maximum_balance_rubles)
        if (gross !== null && cash !== null && maximum !== null && gross - cash <= maximum) cents = gross - cash
    }
    return cents !== null && cents > 0 ? cents / 100 : null
}

export function orderDiscountRows(snapshot?: OrderRead["checkout_snapshot"]) {
    const applications = record(snapshot?.benefits)?.applications
    if (!Array.isArray(applications)) return []
    return applications.flatMap(value => {
        const row = record(value)
        if (!row || typeof row.source_kind !== "string" || row.source_kind === "moysklad_settlement") return []
        const cents = minorUnits(row.discount_amount)
        if (cents === null || cents <= 0) return []
        return [{ source_kind: row.source_kind, code: typeof row.code === "string" ? row.code : null,
            discount_percent: row.discount_percent == null ? null : String(row.discount_percent), amount: cents / 100 }]
    })
}
