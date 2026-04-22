import type {
    WebsiteCoupon,
    WebsiteDiscountEntitlement,
} from "@/services/api/website-identity.types"

export function formatMoney(amount?: number | null, currency?: string | null) {
    if (amount === null || amount === undefined) {
        return null
    }

    if (currency) {
        try {
            return new Intl.NumberFormat("kz.svg-RU", {
                style: "currency",
                currency,
                maximumFractionDigits: 2,
            }).format(amount)
        } catch {
            return `${amount.toFixed(2)} ${currency}`
        }
    }

    return amount.toFixed(2)
}

export function formatEntitlementValue(entitlement: WebsiteDiscountEntitlement, fallback: string) {
    if (entitlement.discount_percent !== null && entitlement.discount_percent !== undefined) {
        return `${entitlement.discount_percent}%`
    }

    if (entitlement.discount_amount !== null && entitlement.discount_amount !== undefined) {
        return formatMoney(entitlement.discount_amount, entitlement.currency) ?? fallback
    }

    return fallback
}

export function formatCouponValue(coupon: WebsiteCoupon, fallback: string) {
    if (coupon.discount_type === "percent" && coupon.discount_value !== null && coupon.discount_value !== undefined) {
        return `${coupon.discount_value}%`
    }

    if (coupon.discount_type === "fixed_amount" && coupon.discount_value !== null && coupon.discount_value !== undefined) {
        return formatMoney(coupon.discount_value, coupon.discount_currency) ?? fallback
    }

    return coupon.discount_rule_name || fallback
}
