export type BenefitCheckPayload = {
    draft_id?: number | null
    code?: string | null
    subtotal?: string | null
    discountable_subtotal?: string | null
    currency?: string | null
    use_bonus_rubles?: boolean
    reward_mode?: "cashback" | "promo" | null
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
    source_external_id: string | null
    benefit_units: string | null
    benefit_unit_name: string | null
    sequence: number | null
    applied_discount_amount: string | null
    subtotal_before: string | null
    subtotal_after: string | null
}

export type BenefitCheckResponse = {
    referral_profile_id: number | null
    reward_program: "bonus" | "partner"
    program_selection_required: boolean
    reward_mode: "cashback" | "promo"
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
    bonus_option: BenefitOptionResponse | null
    bonus_balance_points: number
    bonus_balance_rubles: string
    bonus_pending_points: number
    bonus_pending_rubles: string
    bonus_program_name: string | null
    bonus_max_paid_rate_percent: string
    use_bonus_rubles: boolean
    bonus_applied_points: number
    bonus_applied_rubles: string
    cashback_percent: string
    cashback_earned_points: number
    cashback_expires_in_days: number
}
