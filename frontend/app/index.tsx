import { Redirect } from "expo-router"

import AuthLoadingScreen from "@/components/navigation/auth-loading-screen"
import { ROUTES } from "@/constants/routes"
import { useAuth } from "@/providers/auth-provider"

export default function Index() {
    const { isReady } = useAuth()

    if (!isReady) {
        return <AuthLoadingScreen />
    }

    return <Redirect href={ROUTES.discover} />
}
