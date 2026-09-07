import AuthLoadingScreen from "@/components/navigation/auth-loading-screen"
import HomeScreen from "@/screens/home/home-screen"
import IosHomeScreen from "@/screens/home/ios-home-screen"
import { useAuth } from "@/providers/auth-provider"
import { Platform } from "react-native"

export default function Index() {
    const { isReady } = useAuth()

    if (!isReady) {
        return <AuthLoadingScreen />
    }

    return Platform.OS === "ios" ? <IosHomeScreen /> : <HomeScreen />
}
