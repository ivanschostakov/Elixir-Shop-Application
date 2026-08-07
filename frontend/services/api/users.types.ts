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

export type PresenceHeartbeatResponse = {
    ok: true
    seen_at: string
}

export type CustomerEventName =
    | "app_opened"
    | "product_viewed"
    | "category_viewed"
    | "search_submitted"
    | "banner_clicked"
    | "push_opened"
    | "push_clicked"
    | "cart_item_added"
    | "cart_item_removed"
    | "checkout_started"
    | "checkout_failed"
    | "order_created"
    | "order_paid"
    | "ai_chat_message_sent"
    | "ai_recommendation_shown"
    | "ai_action_clicked"
    | "ai_action_completed"

export type CustomerAttributionPayload = {
    source?: string | null
    medium?: string | null
    campaign?: string | null
    content?: string | null
    term?: string | null
    referrer?: string | null
    landing_page?: string | null
    install_source?: string | null
}

export type CustomerIntelligenceSyncPayload = {
    device?: {
        installation_id: string
        platform: "ios" | "android" | "web"
        app_version?: string | null
        app_build?: string | null
        os_version?: string | null
        device_model?: string | null
        language?: string | null
        timezone?: string | null
        push_permission?: "granted" | "denied" | "undetermined" | "provisional" | "unknown"
        install_source?: string | null
        metadata?: Record<string, unknown>
    }
    consents?: {
        purpose: "analytics" | "marketing" | "personalization"
        channel?: "all" | "push" | "email" | "telegram"
        is_granted: boolean
        source?: "app" | "api" | "worker" | "webhook" | "admin"
        policy_version?: string | null
        changed_at?: string | null
    }[]
    events?: {
        event_id: string
        name: CustomerEventName
        occurred_at: string
        session_id?: string | null
        source?: "app" | "api" | "worker" | "webhook" | "admin"
        entity_type?: string | null
        entity_id?: number | null
        properties?: Record<string, unknown>
        attribution?: CustomerAttributionPayload | null
    }[]
}

export type CustomerIntelligenceSyncResponse = {
    device_id: number | null
    accepted_events: number
    duplicate_events: number
    updated_consents: number
    profile_updated_at: string
}

export type UploadableAvatarImage = {
    uri: string
    fileName?: string | null
    mimeType?: string | null
}

export type ReferralProfileResponse = {
    user_id: number
    reward_program: "bonus" | "partner"
    reward_program_selected_at: string | null
    reward_program_selection_source: string | null
    program_selection_required: boolean
    program_selection_available: boolean
    bitrix_user_id: number | null
    bitrix_profile_found: boolean
    bitrix_sync_status: string
    bitrix_synced_at: string | null
    bonus_program_enabled: boolean
    partner_program_unlocked: boolean
    partner_program_status: "locked" | "eligible" | "active"
    partner_unlock_threshold: string
    partner_unlock_remaining: string
    personal_discount_next_threshold: string | null
    personal_discount_remaining: string
    total_purchases: string
    current_month_purchases: string
    previous_month_purchases: string
    referral_discount_base_total: string
    current_discount_percent: string
    promo_code: string | null
    own_promo_code: string | null
    suggested_promo_code: string | null
    referrer_promo_code: string | null
    bonus_points: number
    bonus_rubles: string
    bonus_wallet_available: boolean
    bonus_program_name: string | null
    bonus_spend_rate_points_to_ruble: number
    bonus_max_paid_rate_percent: string
    bonus_next_expiration_at: string | null
    bonus_expiring_points: number
    bonus_expiring_rubles: string
    bonus_expiry_warning_days: number
    partner_pending_rubles: string
    partner_approved_rubles: string
    partner_rejected_rubles: string
    partner_site_balance_rubles: string
    partner_monthly_minimum: string
    partner_monthly_eligible: boolean
    partner_network_period: string | null
    partner_network_status: string | null
    partner_network_turnover: string
    partner_network_rate_percent: string
    partner_network_amount: string
    created_at: string
    updated_at: string
}

export type ProfilePromotionResponse = {
    kind: "product" | "category"
    title: string
    subtitle: string | null
    discount_percent: string
    image_url: string
    product_id: number
    product_name: string
    category_id: number | null
    category_name: string | null
}

export type ReferrerCodeCheckPayload = {
    code: string
}

export type RewardProgramSelectPayload = {
    program: "bonus" | "partner"
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
