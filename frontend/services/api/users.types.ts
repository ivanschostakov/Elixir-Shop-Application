export type AvatarResponse = {
    image_url: string | null
}

export type PushTokenPlatform = "ios" | "android"

export type UpsertMyPushTokenPayload = {
    expo_push_token: string
    platform: PushTokenPlatform
    current_path?: string | null
}

export type DeleteMyPushTokenPayload = {
    expo_push_token: string
}

export type MyPushTokenResponse = {
    id: number
    user_id: number
    expo_push_token: string
    platform: PushTokenPlatform | null
    current_path: string | null
    created_at: string
    updated_at: string
}

export type DeleteMyPushTokenResponse = {
    ok: boolean
}

export type UploadableAvatarImage = {
    uri: string
    fileName?: string | null
    mimeType?: string | null
}

export type ReferralProfileResponse = {
    user_id: number
    total_purchases: string
    initial_purchase_balance: string
    website_seed_purchase_balance: string
    app_paid_purchase_total: string
    current_month_purchases: string
    previous_month_purchases: string
    current_discount_percent: string
    referrer_promo_code: string | null
    own_promo_code: string | null
    accrued_commissions: string
    deposit_balance: string
    website_seed_metadata: Record<string, unknown>
    created_at: string
    updated_at: string
}

export type ReferrerCodeCheckPayload = {
    code: string
}

export type ReferrerCodeCheckResponse = {
    code: string | null
    is_valid: boolean
    status: string
    reason: string | null
    warning: string | null
    requires_confirmation: boolean
    referrer_user_id: number | null
    depth: number | null
}

export type ReferrerCodeAttachPayload = ReferrerCodeCheckPayload & {
    confirmed?: boolean
}

export type DepositLedgerEntryResponse = {
    id: number
    entry_type: string
    direction: string
    amount: string
    currency: string
    source_system: string
    source_code: string | null
    status: string
    note: string | null
    effective_at: string
    created_at: string
}

export type DepositResponse = {
    balance: string
    currency: string
    ledger_entries: DepositLedgerEntryResponse[]
}
