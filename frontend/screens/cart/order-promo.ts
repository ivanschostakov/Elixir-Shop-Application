import type { BenefitCheckResponse } from "@/services/api/benefits.types"

export function hasAppliedOrderPromo(quote: BenefitCheckResponse | null, code: string | null) {
    const expected = code?.trim().toLowerCase()
    if (!quote || !expected || quote.unresolved_code_reason) return false
    return quote.stacked_discount_options.some(option =>
        option.is_applicable && option.code?.trim().toLowerCase() === expected &&
        Number(option.applied_discount_amount) > 0,
    )
}
