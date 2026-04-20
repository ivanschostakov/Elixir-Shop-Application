import { ENDPOINTS } from "@/services/api/constants"
import { ApiError, apiGet, apiPost } from "@/services/api/client"
import {
    clearAuthTokens,
    getAuthTokens,
    setAuthTokens,
} from "@/services/auth/session"
import type { AuthTokens } from "@/services/auth/session.types"
import type {
    AuthLogoutResponse,
    AuthRefreshPayload,
    AuthTokensWithUserResponse,
    AuthUser,
    BackendAuthTokens,
    BackendAuthUser,
    LoginCredentials,
    RegistrationPayload,
} from "@/services/auth/auth.types"

export type { AuthUser, LoginCredentials, RegistrationPayload } from "@/services/auth/auth.types"

function authPath(path: string) {
    return `${ENDPOINTS.AUTH}${path}`
}

function mapTokens(payload: BackendAuthTokens): AuthTokens {
    return {
        accessToken: payload.access_token,
        refreshToken: payload.refresh_token,
        sessionId: payload.session_id,
    }
}

function mapUser(user: BackendAuthUser): AuthUser {
    const displayName = `${user.name} ${user.surname}`.trim()

    return {
        id: user.id,
        username: user.username,
        email: user.email,
        name: user.name,
        surname: user.surname,
        isActive: user.is_active,
        isVerified: user.is_verified,
        displayName: displayName || user.username,
    }
}

export function getAuthErrorMessage(error: unknown, fallback: string) {
    if (error instanceof ApiError && error.message) {
        return error.message
    }

    if (error instanceof Error && error.message) {
        return error.message
    }

    return fallback
}

export async function authenticate(credentials: LoginCredentials): Promise<AuthUser> {
    const response = await apiPost<AuthTokensWithUserResponse, LoginCredentials>(
        authPath("/login"),
        credentials,
        { auth: false, retryOnUnauthorized: false },
    )

    setAuthTokens(mapTokens(response))
    return mapUser(response.user)
}

export async function registerAccount(payload: RegistrationPayload): Promise<AuthUser> {
    const response = await apiPost<AuthTokensWithUserResponse, RegistrationPayload>(
        authPath("/register"),
        payload,
        { auth: false, retryOnUnauthorized: false },
    )

    setAuthTokens(mapTokens(response))
    return mapUser(response.user)
}

export async function refreshSession(): Promise<AuthTokens | null> {
    const tokens = getAuthTokens()

    if (!tokens) {
        return null
    }

    try {
        const response = await apiPost<BackendAuthTokens, AuthRefreshPayload>(
            authPath("/refresh"),
            {
                session_id: tokens.sessionId,
                refresh_token: tokens.refreshToken,
            },
            { auth: false, retryOnUnauthorized: false },
        )

        const nextTokens = mapTokens(response)
        setAuthTokens(nextTokens)
        return nextTokens
    } catch {
        clearAuthTokens()
        return null
    }
}

export async function logout() {
    const tokens = getAuthTokens()

    if (!tokens) {
        return
    }

    await apiPost<AuthLogoutResponse, AuthRefreshPayload>(
        authPath("/logout"),
        {
            session_id: tokens.sessionId,
            refresh_token: tokens.refreshToken,
        },
        { auth: false, retryOnUnauthorized: false },
    )
}

export async function getCurrentUser(): Promise<AuthUser> {
    const response = await apiGet<BackendAuthUser>(authPath("/me"))
    return mapUser(response)
}
