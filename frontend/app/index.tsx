import { Redirect } from "expo-router"

import AuthLoadingScreen from "@/components/navigation/auth-loading-screen"
import AuthEntryScreen from "@/screens/auth/auth-entry-screen"
import { ROUTES } from "@/constants/routes"
import { useAuth } from "@/providers/auth-provider"

export default function Index() {
    const { isAuthenticated, isReady } = useAuth()

    if (!isReady) {
        return <AuthLoadingScreen />
    }

    if (!isAuthenticated) {
        return <AuthEntryScreen />
    }

    return <Redirect href={ROUTES.discover} />
}
