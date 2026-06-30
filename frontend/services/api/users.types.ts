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
    referral_discount_base_total: string
    current_discount_percent: string
    promo_code: string | null
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
