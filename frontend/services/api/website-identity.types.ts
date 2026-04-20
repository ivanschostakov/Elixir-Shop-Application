export type WebsiteIdentityLoginPayload = {
    login: string
    password: string
}

export type WebsiteReferralProfile = {
    id: number
    website_identity_id: number
    own_promo_code: string | null
    referrer_website_user_id: number | null
    referrer_promo_code: string | null
    referral_percent: number | null
    referral_turnover_amount: number | null
    referral_turnover_currency: string | null
    monthly_paid_orders_amount: number | null
    monthly_paid_orders_currency: string | null
    tier_group_id: number | null
    tier_group_name: string | null
    last_synced_at: string | null
    created_at: string
    updated_at: string
}

export type WebsiteBonusAccount = {
    id: number
    website_identity_id: number
    website_bonus_account_external_id: number | null
    is_active: boolean
    balance: number
    currency: string | null
    website_created_at: string | null
    last_synced_at: string | null
    created_at: string
    updated_at: string
}

export type WebsiteDiscountEntitlement = {
    id: number
    website_identity_id: number
    source_kind: string
    website_source_id: string | null
    source_name: string
    discount_percent: number | null
    discount_amount: number | null
    currency: string | null
    priority: number | null
    is_stackable: boolean
    is_active: boolean
    starts_at: string | null
    ends_at: string | null
    last_synced_at: string | null
    created_at: string
    updated_at: string
}

export type WebsiteCoupon = {
    id: number
    website_identity_id: number
    website_coupon_external_id: number | null
    coupon_code: string
    discount_rule_id: number | null
    discount_rule_name: string | null
    discount_type: string | null
    discount_value: number | null
    discount_currency: string | null
    max_use: number | null
    use_count: number
    is_active: boolean
    description: string | null
    website_created_at: string | null
    website_applied_at: string | null
    last_synced_at: string | null
    created_at: string
    updated_at: string
}

export type WebsiteIdentity = {
    id: number
    user_id: number
    website_user_id: number
    website_login: string
    website_email: string | null
    website_name: string | null
    website_last_name: string | null
    website_second_name: string | null
    website_phone: string | null
    website_mobile: string | null
    website_city: string | null
    website_registered_at: string | null
    website_last_login_at: string | null
    group_ids: number[]
    group_names: string[]
    custom_fields: Record<string, string>
    referral_program: Record<string, unknown> | null
    bonus_account: Record<string, unknown> | null
    discount_groups: Record<string, unknown>[]
    active_coupons: Record<string, unknown>[]
    recent_used_coupons: Record<string, unknown>[]
    raw_payload: Record<string, unknown> | null
    last_synced_at: string | null
    referral_profile: WebsiteReferralProfile | null
    bonus_account_snapshot: WebsiteBonusAccount | null
    discount_entitlements: WebsiteDiscountEntitlement[]
    coupon_snapshots: WebsiteCoupon[]
    created_at: string
    updated_at: string
}
