import AuthLoadingScreen from "@/components/navigation/auth-loading-screen"
import HomeScreen from "@/screens/home/home-screen"
import { useAuth } from "@/providers/auth-provider"

export default function Index() {
    const { isReady } = useAuth()

    if (!isReady) {
        return <AuthLoadingScreen />
    }

    return <HomeScreen />
}
