export type AvatarResponse = {
    image_url: string | null
}

export type PushTokenPlatform = "ios" | "android"

export type UpsertMyPushTokenPayload = {
    expo_push_token: string
    platform: PushTokenPlatform
}

export type DeleteMyPushTokenPayload = {
    expo_push_token: string
}

export type MyPushTokenResponse = {
    id: number
    user_id: number
    expo_push_token: string
    platform: PushTokenPlatform | null
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
