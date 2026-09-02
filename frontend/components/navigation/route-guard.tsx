import { useEffect, useRef } from "react"
import { Redirect, useLocalSearchParams, usePathname, useRouter } from "expo-router"

import AuthLoadingScreen from "@/components/navigation/auth-loading-screen"
import { showAuthRequiredAlert } from "@/components/navigation/auth-required-alert"
import type { RouteGuardProps } from "@/components/navigation/route-guard.types"
import { ROUTES, isAccountRequiredRoute } from "@/constants/routes"
import { useAuth } from "@/providers/auth-provider"
import { isCatalogRoute, useCatalogAvailable } from "@/services/app-features"

export function CatalogRoute({ children }: RouteGuardProps) {
    const available = useCatalogAvailable()
    return available ? children : <Redirect href={ROUTES.home} />
}

export function ProtectedRoute({ children, redirectTo = ROUTES.home }: RouteGuardProps) {
    const pathname = usePathname()
    const { orderId } = useLocalSearchParams<{ orderId?: string }>()
    const catalogAvailable = useCatalogAvailable()
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

    const viewingExistingOrder = pathname === ROUTES.payment && /^\d+$/.test(orderId ?? "") && Number(orderId) > 0
    if (!catalogAvailable && isCatalogRoute(pathname) && !viewingExistingOrder) {
        return <Redirect href={ROUTES.home} />
    }

    if (!isAuthenticated && isAccountRequiredRoute(pathname)) {
        return <Redirect href={redirectTo} />
    }

    return children
}

export function GuestRoute({ children, redirectTo = ROUTES.discover }: RouteGuardProps) {
    const { isAuthenticated, isReady } = useAuth()
    const catalogAvailable = useCatalogAvailable()

    if (!isReady) {
        return <AuthLoadingScreen />
    }

    if (isAuthenticated) {
        return <Redirect href={!catalogAvailable && isCatalogRoute(String(redirectTo)) ? ROUTES.home : redirectTo} />
    }

    return children
}
