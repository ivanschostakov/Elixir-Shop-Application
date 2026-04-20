import { ActivityIndicator, View } from "react-native"

import { authLoadingScreenStyles } from "@/components/navigation/auth-loading-screen.styles"
import { colors } from "@/theme/colors"
export default function AuthLoadingScreen() {
    return (
        <View style={authLoadingScreenStyles.container}>
            <ActivityIndicator color={colors.primary} size="large" />
        </View>
    )
}
