import { ActivityIndicator, View } from "react-native"

import { authLoadingScreenStyles } from "@/components/navigation/auth-loading-screen.styles"
import { useTheme } from "@/providers/theme-provider"
export default function AuthLoadingScreen() {
    const { palette } = useTheme()
    return (
        <View style={authLoadingScreenStyles.container}>
            <ActivityIndicator color={palette.primary} size="large" />
        </View>
    )
}
