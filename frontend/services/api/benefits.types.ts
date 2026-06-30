export type BenefitCheckPayload = {
    code?: string | null
    subtotal?: string | null
    discountable_subtotal?: string | null
    currency?: string | null
}

export type BenefitOptionResponse = {
    source_kind: string
    source_record_id: number | null
    code: string | null
    title: string
    status: string
    is_applicable: boolean
    is_personal: boolean
    is_stackable: boolean
    calculation_mode: string
    discount_percent: string | null
    discount_amount: string | null
    currency: string | null
    estimated_discount_amount: string | null
    estimated_total_after: string | null
    reason: string | null
    sequence: number | null
    applied_discount_amount: string | null
    subtotal_before: string | null
    subtotal_after: string | null
}

export type BenefitCheckResponse = {
    referral_profile_id: number | null
    subtotal_source: string
    basket_subtotal: string
    currency: string | null
    entered_code: string | null
    entered_code_matches: BenefitOptionResponse[]
    unresolved_code_reason: string | null
    available_discount_options: BenefitOptionResponse[]
    personal_discount: BenefitOptionResponse | null
    best_discount: BenefitOptionResponse | null
    stacked_discount_options: BenefitOptionResponse[]
    stacked_discount_amount: string
    total_after_discounts: string
}
