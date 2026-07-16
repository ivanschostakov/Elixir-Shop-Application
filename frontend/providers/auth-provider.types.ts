import type { ReactNode } from "react"

import type {
    AuthUser,
    AuthTokensWithUserResponse,
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

export type AuthContextValue = {
    isReady: boolean
    isAuthenticated: boolean
    user: AuthUser | null
    signIn: (credentials: LoginCredentials) => Promise<LoginResult>
    verifyLogin: (payload: LoginVerifyPayload) => Promise<void>
    resendLoginCode: (payload: LoginCredentials) => Promise<LoginVerificationRequiredResponse>
    register: (payload: RegistrationPayload) => Promise<RegistrationStartedResponse>
    verifyRegistration: (payload: RegistrationVerifyPayload) => Promise<void>
    resendRegistrationCode: (payload: RegistrationCodeResendPayload) => Promise<RegistrationCodeSentResponse>
    acceptSession: (response: AuthTokensWithUserResponse) => AuthUser
    updatePersonalData: (payload: PersonalDataUpdatePayload) => Promise<AuthUser>
    signOut: () => Promise<void>
    deleteAccount: () => Promise<void>
}

export type AuthProviderProps = {
    children: ReactNode
}
