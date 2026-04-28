import type { AuthTokens } from "@/services/auth/session.types"

export type LoginCredentials = {
    login: string
    password: string
}

export type LoginVerifyPayload = {
    email: string
    code: string
}

export type LoginVerificationRequiredResponse = {
    email: string
    verification_required: boolean
    message: string
}

export type LoginResult =
    | {
          verificationRequired: false
          user: AuthUser
      }
    | {
          verificationRequired: true
          email: string
          message: string
      }

export type RegistrationPayload = {
    username: string
    email: string
    password: string
    name: string
    surname: string
}

export type RegistrationStartedResponse = {
    user_id: number
    email: string
    verification_required: boolean
    message: string
}

export type RegistrationVerifyPayload = {
    email: string
    code: string
}

export type RegistrationCodeResendPayload = {
    email: string
}

export type RegistrationCodeSentResponse = {
    email: string
    verification_required: boolean
    message: string
}

export type BackendAuthUser = {
    id: number
    username: string
    email: string
    name: string
    surname: string
    phone_number: string | null
    is_active: boolean
    is_verified: boolean
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

export type BackendLoginResponse = AuthTokensWithUserResponse | LoginVerificationRequiredResponse

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
    username: string
    email: string
    name: string
    surname: string
    phoneNumber: string | null
    isActive: boolean
    isVerified: boolean
    displayName: string
}

export type MapTokens = (payload: BackendAuthTokens) => AuthTokens
