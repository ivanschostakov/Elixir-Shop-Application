import { useEffect, useState } from "react"
import { usePathname } from "expo-router"
import { AppState, type AppStateStatus } from "react-native"

import {
    authenticate,
    getCurrentUser,
    getAuthErrorMessage,
    logout,
    refreshSession,
    registerAccount,
    resendLoginCode as resendLoginCodeRequest,
    resendRegistrationCode as resendRegistrationCodeRequest,
    verifyLogin as verifyLoginRequest,
    verifyRegistration as verifyRegistrationRequest,
} from "@/services/auth/auth"
import { translate } from "@/i18n/translations"
import { clearBasketSnapshot } from "@/hooks/basket/basket-store"
import { AuthContext } from "@/providers/auth-provider.context"
import type { AuthProviderProps } from "@/providers/auth-provider.types"
import {
    resetOrderStatusNotifications,
    setOrderStatusNotificationCurrentPath,
    syncOrderStatusNotifications,
    unregisterOrderStatusNotifications,
} from "@/services/notifications/order-status-notifications"
import type {
    AuthUser,
    LoginCredentials,
    LoginResult,
    LoginVerifyPayload,
    RegistrationCodeResendPayload,
    RegistrationPayload,
    RegistrationVerifyPayload,
} from "@/services/auth/auth.types"
import {
    clearAuthTokens,
    getAuthTokens,
    hydrateAuthTokens,
    setRefreshHandler,
    subscribeAuthSession,
} from "@/services/auth/session"

function normalizeAuthErrorMessage(rawMessage: string, fallbackMessage: string) {
    const normalizedMessage = rawMessage.trim()
    const loweredMessage = normalizedMessage.toLowerCase()

    if (!normalizedMessage) {
        return fallbackMessage
    }

    if (
        loweredMessage.includes("invalid credentials") ||
        loweredMessage.includes("invalid website credentials") ||
        loweredMessage.includes("could not validate credentials")
    ) {
        return translate("auth.error.invalidCredentials")
    }

    if (
        loweredMessage.includes("invalid verification code") ||
        loweredMessage.includes("invalid or expired verification code")
    ) {
        return translate("auth.error.invalidCode")
    }

    if (
        loweredMessage.includes("<!doctype html") ||
        loweredMessage.includes("<html") ||
        loweredMessage.includes("unexpected token '<'") ||
        loweredMessage.includes("failed to fetch") ||
        loweredMessage.includes("network request failed") ||
        loweredMessage.includes("request timed out")
    ) {
        return translate("auth.error.backendUnavailable")
    }

    return normalizedMessage
}

function mapAuthErrorMessage(error: unknown, fallbackMessage: string) {
    const rawMessage = getAuthErrorMessage(error, fallbackMessage)
    return normalizeAuthErrorMessage(rawMessage, fallbackMessage)
}

export function AuthProvider({ children }: AuthProviderProps) {
    const [user, setUser] = useState<AuthUser | null>(null)
    const [isReady, setIsReady] = useState(false)
    const pathname = usePathname()

    useEffect(() => {
        return subscribeAuthSession((tokens) => {
            if (!tokens) {
                clearBasketSnapshot()
                resetOrderStatusNotifications()
                setUser(null)
            }
        })
    }, [])

    useEffect(() => {
        if (!user) {
            resetOrderStatusNotifications()
            setOrderStatusNotificationCurrentPath(null)
            return
        }

        void syncOrderStatusNotifications()
    }, [user])

    useEffect(() => {
        if (!user) {
            setOrderStatusNotificationCurrentPath(null)
            return
        }

        setOrderStatusNotificationCurrentPath(pathname)
        void syncOrderStatusNotifications()
    }, [pathname, user])

    useEffect(() => {
        if (!user) {
            return
        }

        let previousAppState: AppStateStatus = AppState.currentState
        const appStateSubscription = AppState.addEventListener("change", (nextAppState) => {
            if (previousAppState === nextAppState) {
                return
            }
            previousAppState = nextAppState

            if (nextAppState === "active") {
                setOrderStatusNotificationCurrentPath(pathname)
            } else {
                setOrderStatusNotificationCurrentPath(null)
            }
            void syncOrderStatusNotifications()
        })

        return () => {
            appStateSubscription.remove()
        }
    }, [pathname, user])

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
                clearBasketSnapshot()

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

    const signIn = async (credentials: LoginCredentials): Promise<LoginResult> => {
        try {
            const result = await authenticate(credentials)
            if (!result.verificationRequired) {
                setUser(result.user)
            }
            return result
        } catch (error) {
            clearAuthTokens()
            throw new Error(mapAuthErrorMessage(error, translate("auth.error.loginFallback")))
        }
    }

    const register = async (payload: RegistrationPayload) => {
        try {
            return await registerAccount(payload)
        } catch (error) {
            clearAuthTokens()
            throw new Error(mapAuthErrorMessage(error, translate("auth.error.registerFallback")))
        }
    }

    const verifyLogin = async (payload: LoginVerifyPayload) => {
        try {
            const nextUser = await verifyLoginRequest(payload)
            setUser(nextUser)
        } catch (error) {
            clearAuthTokens()
            throw new Error(mapAuthErrorMessage(error, translate("auth.error.verifyFallback")))
        }
    }

    const resendLoginCode = async (payload: LoginCredentials) => {
        try {
            return await resendLoginCodeRequest(payload)
        } catch (error) {
            throw new Error(mapAuthErrorMessage(error, translate("auth.error.resendCodeFallback")))
        }
    }

    const verifyRegistration = async (payload: RegistrationVerifyPayload) => {
        try {
            const nextUser = await verifyRegistrationRequest(payload)
            setUser(nextUser)
        } catch (error) {
            clearAuthTokens()
            throw new Error(mapAuthErrorMessage(error, translate("auth.error.verifyFallback")))
        }
    }

    const resendRegistrationCode = async (payload: RegistrationCodeResendPayload) => {
        try {
            return await resendRegistrationCodeRequest(payload)
        } catch (error) {
            throw new Error(mapAuthErrorMessage(error, translate("auth.error.resendCodeFallback")))
        }
    }

    const signOut = async () => {
        try {
            await unregisterOrderStatusNotifications()
            await logout()
        } finally {
            clearAuthTokens()
            clearBasketSnapshot()
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
                verifyLogin,
                resendLoginCode,
                register,
                verifyRegistration,
                resendRegistrationCode,
                signOut,
            }}
        >
            {children}
        </AuthContext.Provider>
    )
}

export { useAuth } from "@/providers/auth-provider.context"
