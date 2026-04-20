import type { ReactNode } from "react"

import type { AuthUser, LoginCredentials, RegistrationPayload } from "@/services/auth/auth.types"

export type AuthContextValue = {
    isReady: boolean
    isAuthenticated: boolean
    user: AuthUser | null
    signIn: (credentials: LoginCredentials) => Promise<void>
    register: (payload: RegistrationPayload) => Promise<void>
    signOut: () => Promise<void>
}

export type AuthProviderProps = {
    children: ReactNode
}
