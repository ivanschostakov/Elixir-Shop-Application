import { useEffect, useState } from "react"

import {
    authenticate,
    getCurrentUser,
    getAuthErrorMessage,
    logout,
    refreshSession,
    registerAccount,
} from "@/services/auth/auth"
import { translate } from "@/i18n/translations"
import { AuthContext } from "@/providers/auth-provider.context"
import type { AuthProviderProps } from "@/providers/auth-provider.types"
import {
    resetOrderStatusNotifications,
    syncOrderStatusNotifications,
    unregisterOrderStatusNotifications,
} from "@/services/notifications/order-status-notifications"
import type { AuthUser, LoginCredentials, RegistrationPayload } from "@/services/auth/auth.types"
import {
    clearAuthTokens,
    getAuthTokens,
    hydrateAuthTokens,
    setRefreshHandler,
    subscribeAuthSession,
} from "@/services/auth/session"

export function AuthProvider({ children }: AuthProviderProps) {
    const [user, setUser] = useState<AuthUser | null>(null)
    const [isReady, setIsReady] = useState(false)

    useEffect(() => {
        return subscribeAuthSession((tokens) => {
            if (!tokens) {
                resetOrderStatusNotifications()
                setUser(null)
            }
        })
    }, [])

    useEffect(() => {
        if (!user) {
            resetOrderStatusNotifications()
            return
        }

        void syncOrderStatusNotifications()
    }, [user])

    useEffect(() => {
        let isMounted = true

        setRefreshHandler(refreshSession)

        const restoreSession = async () => {
            await hydrateAuthTokens()

            if (!getAuthTokens()) {
                if (isMounted) {
                    setIsReady(true)
                }
                return
            }

            try {
                const nextUser = await getCurrentUser()

                if (isMounted) {
                    setUser(nextUser)
                }
            } catch {
                clearAuthTokens()

                if (isMounted) {
                    setUser(null)
                }
            } finally {
                if (isMounted) {
                    setIsReady(true)
                }
            }
        }

        void restoreSession()

        return () => {
            isMounted = false
            setRefreshHandler(null)
        }
    }, [])

    const signIn = async (credentials: LoginCredentials) => {
        try {
            const nextUser = await authenticate(credentials)
            setUser(nextUser)
        } catch (error) {
            clearAuthTokens()
            throw new Error(getAuthErrorMessage(error, translate("auth.error.loginFallback")))
        }
    }

    const register = async (payload: RegistrationPayload) => {
        try {
            const nextUser = await registerAccount(payload)
            setUser(nextUser)
        } catch (error) {
            clearAuthTokens()
            throw new Error(getAuthErrorMessage(error, translate("auth.error.registerFallback")))
        }
    }

    const signOut = async () => {
        try {
            await unregisterOrderStatusNotifications()
            await logout()
        } finally {
            clearAuthTokens()
            resetOrderStatusNotifications()
            setUser(null)
        }
    }

    const isAuthenticated = Boolean(user)

    return (
        <AuthContext.Provider
            value={{
                isReady,
                isAuthenticated,
                user,
                signIn,
                register,
                signOut,
            }}
        >
            {children}
        </AuthContext.Provider>
    )
}

export { useAuth } from "@/providers/auth-provider.context"
