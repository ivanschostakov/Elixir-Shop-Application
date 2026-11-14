import type { TranslationKey } from "@/i18n/translations"
import type { BenefitOptionResponse } from "@/services/api/benefits.types"

export function formatAppliedDiscount(option: BenefitOptionResponse, t: (key: TranslationKey) => string) {
    const isBalance = option.source_kind === "moysklad_bonus" || option.source_kind === "moysklad_settlement"
    const isPromo = !isBalance && Boolean(option.code || option.source_kind === "app_referral" || option.source_kind === "bitrix_promo")
    const label = t(isPromo ? "checkout.promoCodeTitle" : isBalance ? "checkout.bonusRublesTitle" : "checkout.discountTitle")
    const percent = Number(option.discount_percent)
    const code = isPromo && option.code ? ` ${option.code}` : ""
    return `${label}${code}${!isBalance && percent > 0 ? ` −${String(percent).replace(".", ",")}%` : ""}`
}
