import { Redirect } from "expo-router"

import AuthLoadingScreen from "@/components/navigation/auth-loading-screen"
import type { RouteGuardProps } from "@/components/navigation/route-guard.types"
import { ROUTES } from "@/constants/routes"
import { useAuth } from "@/providers/auth-provider"

export function ProtectedRoute({ children, redirectTo = ROUTES.home }: RouteGuardProps) {
    const { isAuthenticated, isReady } = useAuth()

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
