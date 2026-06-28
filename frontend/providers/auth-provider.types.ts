import type { ReactNode } from "react"

import type {
    AuthUser,
    AuthTokensWithUserResponse,
    LoginCredentials,
    PersonalDataUpdatePayload,
    PhoneAuthStartPayload,
    PhoneAuthStartResponse,
    PhoneAuthSetupResponse,
    PhoneAuthVerificationPayload,
    PhoneAuthVerificationRequiredResponse,
    PhoneClaimPayload,
    PhoneRegisterPayload,
} from "@/services/auth/auth.types"

export type AuthContextValue = {
    isReady: boolean
    isAuthenticated: boolean
    user: AuthUser | null
    startPhoneAuth: (payload: PhoneAuthStartPayload) => Promise<PhoneAuthStartResponse>
    signIn: (credentials: LoginCredentials) => Promise<AuthUser>
    claimPhoneAccount: (payload: PhoneClaimPayload) => Promise<PhoneAuthSetupResponse>
    registerPhoneAccount: (payload: PhoneRegisterPayload) => Promise<PhoneAuthSetupResponse>
    verifyPhoneAuth: (payload: PhoneAuthVerificationPayload) => Promise<void>
    resendPhoneAuthCode: (payload: PhoneAuthStartPayload) => Promise<PhoneAuthVerificationRequiredResponse>
    acceptSession: (response: AuthTokensWithUserResponse) => AuthUser
    updatePersonalData: (payload: PersonalDataUpdatePayload) => Promise<AuthUser>
    signOut: () => Promise<void>
    deleteAccount: () => Promise<void>
}

export type AuthProviderProps = {
    children: ReactNode
}
