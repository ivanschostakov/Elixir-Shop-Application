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
    AuthTokensWithUserResponse,
    AuthUser,
    BackendLoginResponse,
    BackendAuthTokens,
    BackendAuthUser,
    LoginCredentials,
    LoginResult,
    LoginVerificationRequiredResponse,
    LoginVerifyPayload,
    PersonalDataUpdatePayload,
    RegistrationCodeResendPayload,
    RegistrationCodeSentResponse,
    RegistrationPayload,
    RegistrationStartedResponse,
    RegistrationVerifyPayload,
} from "@/services/auth/auth.types"

export type {
    AuthUser,
    LoginCredentials,
    LoginResult,
    LoginVerificationRequiredResponse,
    LoginVerifyPayload,
    PersonalDataUpdatePayload,
    RegistrationCodeResendPayload,
    RegistrationPayload,
    RegistrationStartedResponse,
    RegistrationVerifyPayload,
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
        username: user.username,
        email: user.email,
        name: user.name,
        surname: user.surname,
        phoneNumber: user.phone_number,
        isActive: user.is_active,
        isVerified: user.is_verified,
        displayName: displayName || user.username,
    }
}

function isLoginVerificationRequired(response: BackendLoginResponse): response is Extract<BackendLoginResponse, { verification_required: boolean }> {
    return "verification_required" in response && response.verification_required
}

export async function authenticate(credentials: LoginCredentials): Promise<LoginResult> {
    const response = await apiPost<BackendLoginResponse, LoginCredentials>(
        authPath("/login"),
        credentials,
        { auth: false, retryOnUnauthorized: false },
    )

    if (isLoginVerificationRequired(response)) {
        return {
            verificationRequired: true,
            email: response.email,
            message: response.message,
        }
    }

    setAuthTokens(mapTokens(response))
    return {
        verificationRequired: false,
        user: mapUser(response.user),
    }
}

export function applyAuthTokensWithUser(response: AuthTokensWithUserResponse): AuthUser {
    setAuthTokens(mapTokens(response))
    return mapUser(response.user)
}

export async function verifyLogin(payload: LoginVerifyPayload): Promise<AuthUser> {
    const response = await apiPost<AuthTokensWithUserResponse, LoginVerifyPayload>(
        authPath("/login/verify"),
        payload,
        { auth: false, retryOnUnauthorized: false },
    )

    setAuthTokens(mapTokens(response))
    return mapUser(response.user)
}

export async function resendLoginCode(payload: LoginCredentials): Promise<LoginVerificationRequiredResponse> {
    return apiPost<LoginVerificationRequiredResponse, LoginCredentials>(
        authPath("/login/resend-code"),
        payload,
        { auth: false, retryOnUnauthorized: false },
    )
}

export async function registerAccount(payload: RegistrationPayload): Promise<RegistrationStartedResponse> {
    return apiPost<RegistrationStartedResponse, RegistrationPayload>(
        authPath("/register"),
        payload,
        { auth: false, retryOnUnauthorized: false },
    )
}

export async function verifyRegistration(payload: RegistrationVerifyPayload): Promise<AuthUser> {
    const response = await apiPost<AuthTokensWithUserResponse, RegistrationVerifyPayload>(
        authPath("/register/verify"),
        payload,
        { auth: false, retryOnUnauthorized: false },
    )

    setAuthTokens(mapTokens(response))
    return mapUser(response.user)
}

export async function resendRegistrationCode(payload: RegistrationCodeResendPayload): Promise<RegistrationCodeSentResponse> {
    return apiPost<RegistrationCodeSentResponse, RegistrationCodeResendPayload>(
        authPath("/register/resend-code"),
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
