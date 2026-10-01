import { View } from "react-native"

import { authLoadingScreenStyles } from "@/components/navigation/auth-loading-screen.styles"
import { QuietLoading } from "@/components/ui/quiet-loading"
export default function AuthLoadingScreen() {
    return (
        <View style={authLoadingScreenStyles.container}>
            <QuietLoading loading kind="content" />
        </View>
    )
}
