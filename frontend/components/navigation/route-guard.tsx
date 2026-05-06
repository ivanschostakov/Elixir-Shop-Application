import { useEffect, useRef } from "react"
import { Redirect, usePathname, useRouter } from "expo-router"

import AuthLoadingScreen from "@/components/navigation/auth-loading-screen"
import { showAuthRequiredAlert } from "@/components/navigation/auth-required-alert"
import type { RouteGuardProps } from "@/components/navigation/route-guard.types"
import { ROUTES, isAccountRequiredRoute } from "@/constants/routes"
import { useAuth } from "@/providers/auth-provider"

export function ProtectedRoute({ children, redirectTo = ROUTES.home }: RouteGuardProps) {
    const pathname = usePathname()
    const router = useRouter()
    const { isAuthenticated, isReady } = useAuth()
    const didShowLoginPromptRef = useRef(false)

    useEffect(() => {
        if (!isReady || isAuthenticated || didShowLoginPromptRef.current) {
            return
        }

        if (!isAccountRequiredRoute(pathname)) {
            return
        }

        didShowLoginPromptRef.current = true
        showAuthRequiredAlert({
            onLogin: () => {
                router.push(ROUTES.login)
            },
        })
    }, [isAuthenticated, isReady, pathname, router])

    if (!isReady) {
        return <AuthLoadingScreen />
    }

    if (!isAuthenticated) {
        return <Redirect href={redirectTo} />
    }

    return children
}

export function GuestRoute({ children, redirectTo = ROUTES.discover }: RouteGuardProps) {
    const { isAuthenticated, isReady } = useAuth()

    if (!isReady) {
        return <AuthLoadingScreen />
    }

    if (isAuthenticated) {
        return <Redirect href={redirectTo} />
    }

    return children
}
