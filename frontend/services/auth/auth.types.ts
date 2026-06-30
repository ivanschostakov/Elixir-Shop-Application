import type { AuthTokens } from "@/services/auth/session.types"

export type LoginCredentials = {
    phone_number: string
    password: string
}

export type PhoneAuthStartPayload = {
    phone_number: string
}

export type PhoneAuthStartStep = "login" | "claim" | "register"

export type PhoneAuthStartResponse = {
    phone_number: string
    next_step: PhoneAuthStartStep
    email_required: boolean
    email_hint: string | null
    message: string
}

export type PhoneAuthVerificationPayload = {
    phone_number: string
    code: string
}

export type PhoneAuthVerificationRequiredResponse = {
    phone_number: string
    email: string | null
    verification_required: boolean
    message: string
}

export type PhoneAuthSetupResponse = PhoneAuthVerificationRequiredResponse | AuthTokensWithUserResponse

export type PhoneClaimPayload = {
    phone_number: string
    password: string
    email?: string | null
}

export type PhoneRegisterPayload = {
    phone_number: string
    email?: string | null
    password: string
    name: string
    surname: string
}

export type BackendAuthUser = {
    id: number
    email: string | null
    name: string
    surname: string
    phone_number: string
    is_active: boolean
    is_verified: boolean
    promo_code: string | null
}

export type BackendAuthTokens = {
    access_token: string
    refresh_token: string
    session_id: number
    token_type: "bearer"
}

export type AuthTokensWithUserResponse = BackendAuthTokens & {
    user: BackendAuthUser
}

export type TelegramAuthPayload = {
    init_data: string
}

export type TelegramAuthContactRequiredResponse = {
    contact_required: true
    telegram_user_id: number
    message: string
}

export type TelegramAuthResponse = AuthTokensWithUserResponse | TelegramAuthContactRequiredResponse

export type AuthLogoutResponse = {
    ok: boolean
    message: string
}

export type AuthRefreshPayload = {
    session_id: number
    refresh_token: string
}

export type AuthUser = {
    id: number
    email: string | null
    name: string
    surname: string
    phoneNumber: string
    isActive: boolean
    isVerified: boolean
    promoCode: string | null
    displayName: string
}

export type PersonalDataUpdatePayload = {
    email?: string | null
    name?: string
    surname?: string
    phone_number?: string
    password?: string
}

export type MapTokens = (payload: BackendAuthTokens) => AuthTokens
