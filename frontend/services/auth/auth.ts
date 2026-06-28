import { ENDPOINTS } from "@/services/api/constants"
import { apiDelete, apiGet, apiPatch, apiPost } from "@/services/api/client"
import {
    clearAuthTokens,
    getAuthTokens,
    setAuthTokens,
} from "@/services/auth/session"
import type { AuthTokens } from "@/services/auth/session.types"
import type {
    AuthLogoutResponse,
    AuthRefreshPayload,
    PhoneAuthSetupResponse,
    AuthTokensWithUserResponse,
    AuthUser,
    BackendAuthTokens,
    BackendAuthUser,
    LoginCredentials,
    PersonalDataUpdatePayload,
    PhoneAuthStartPayload,
    PhoneAuthStartResponse,
    PhoneAuthVerificationPayload,
    PhoneAuthVerificationRequiredResponse,
    PhoneClaimPayload,
    PhoneRegisterPayload,
} from "@/services/auth/auth.types"

export type {
    AuthUser,
    LoginCredentials,
    PersonalDataUpdatePayload,
    PhoneAuthStartPayload,
    PhoneAuthStartResponse,
    PhoneAuthVerificationPayload,
    PhoneAuthVerificationRequiredResponse,
    PhoneClaimPayload,
    PhoneRegisterPayload,
} from "@/services/auth/auth.types"
export { getErrorMessage as getAuthErrorMessage } from "@/utils/errors"

function authPath(path: string) {
    return `${ENDPOINTS.AUTH}${path}`
}

function usersPath(path: string) {
    return `${ENDPOINTS.USERS}${path}`
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
        email: user.email,
        name: user.name,
        surname: user.surname,
        phoneNumber: user.phone_number,
        isActive: user.is_active,
        isVerified: user.is_verified,
        displayName: displayName || user.phone_number || user.email || `User #${user.id}`,
    }
}

function phoneAuthPath(path: string) {
    return authPath(`/phone${path}`)
}

export async function startPhoneAuth(payload: PhoneAuthStartPayload): Promise<PhoneAuthStartResponse> {
    return apiPost<PhoneAuthStartResponse, PhoneAuthStartPayload>(
        phoneAuthPath("/start"),
        payload,
        { auth: false, retryOnUnauthorized: false },
    )
}

export function applyAuthTokensWithUser(response: AuthTokensWithUserResponse): AuthUser {
    setAuthTokens(mapTokens(response))
    return mapUser(response.user)
}

export async function loginWithPhone(credentials: LoginCredentials): Promise<AuthUser> {
    const response = await apiPost<AuthTokensWithUserResponse, LoginCredentials>(
        phoneAuthPath("/login"),
        credentials,
        { auth: false, retryOnUnauthorized: false },
    )

    setAuthTokens(mapTokens(response))
    return mapUser(response.user)
}

export async function claimPhoneAccount(payload: PhoneClaimPayload): Promise<PhoneAuthSetupResponse> {
    return apiPost<PhoneAuthSetupResponse, PhoneClaimPayload>(
        phoneAuthPath("/claim"),
        payload,
        { auth: false, retryOnUnauthorized: false },
    )
}

export async function registerPhoneAccount(payload: PhoneRegisterPayload): Promise<PhoneAuthSetupResponse> {
    return apiPost<PhoneAuthSetupResponse, PhoneRegisterPayload>(
        phoneAuthPath("/register"),
        payload,
        { auth: false, retryOnUnauthorized: false },
    )
}

export async function verifyPhoneAuth(payload: PhoneAuthVerificationPayload): Promise<AuthUser> {
    const response = await apiPost<AuthTokensWithUserResponse, PhoneAuthVerificationPayload>(
        phoneAuthPath("/verify"),
        payload,
        { auth: false, retryOnUnauthorized: false },
    )

    setAuthTokens(mapTokens(response))
    return mapUser(response.user)
}

export async function resendPhoneAuthCode(payload: PhoneAuthStartPayload): Promise<PhoneAuthVerificationRequiredResponse> {
    return apiPost<PhoneAuthVerificationRequiredResponse, PhoneAuthStartPayload>(
        phoneAuthPath("/resend-code"),
        payload,
        { auth: false, retryOnUnauthorized: false },
    )
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

export async function deleteAccount() {
    await apiDelete<AuthLogoutResponse>(authPath("/me"))
}

export async function getCurrentUser(): Promise<AuthUser> {
    const response = await apiGet<BackendAuthUser>(authPath("/me"))
    return mapUser(response)
}

export async function updateCurrentUserPersonalData(payload: PersonalDataUpdatePayload): Promise<AuthUser> {
    const response = await apiPatch<BackendAuthUser, PersonalDataUpdatePayload>(
        usersPath("/me/profile/personal-data"),
        payload,
    )
    return mapUser(response)
}
