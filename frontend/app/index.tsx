import AuthLoadingScreen from "@/components/navigation/auth-loading-screen"
import AuthEntryScreen from "@/screens/auth/auth-entry-screen"
import { useAuth } from "@/providers/auth-provider"

import HomeScreen from "../screens/home/home-screen"

export default function Index() {
    const { isAuthenticated, isReady } = useAuth()

    if (!isReady) {
        return <AuthLoadingScreen />
    }

    if (!isAuthenticated) {
        return <AuthEntryScreen />
    }

    return <HomeScreen />
}
