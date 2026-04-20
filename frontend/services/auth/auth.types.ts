import type { AuthTokens } from "@/services/auth/session.types"

export type LoginCredentials = {
    login: string
    password: string
}

export type RegistrationPayload = {
    username: string
    email: string
    password: string
    name: string
    surname: string
}

export type BackendAuthUser = {
    id: number
    username: string
    email: string
    name: string
    surname: string
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
    isActive: boolean
    isVerified: boolean
    displayName: string
}

export type MapTokens = (payload: BackendAuthTokens) => AuthTokens
