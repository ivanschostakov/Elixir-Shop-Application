import type {
    WebsiteCoupon,
    WebsiteDiscountEntitlement,
} from "@/services/api/website-identity.types"
import { formatMoney } from "@/utils/formatting"

export { formatMoney }

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
