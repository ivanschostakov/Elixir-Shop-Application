import { Pressable, ScrollView, Text, View } from "react-native"
import { router } from "expo-router"
import { SafeAreaView } from "react-native-safe-area-context"

import { ROUTES } from "@/constants/routes"
import { useLanguage } from "@/providers/language-provider"
import { authSharedStyles } from "@/screens/auth/auth-shared.styles"

export default function AuthEntryScreen() {
    const { t } = useLanguage()

    return (
        <SafeAreaView style={authSharedStyles.container}>
            <ScrollView contentContainerStyle={authSharedStyles.content}>
                <View style={authSharedStyles.card}>
                    <Text style={authSharedStyles.title}>{t("app.name")}</Text>

                    <Pressable
                        onPress={() => router.push(ROUTES.login)}
                        style={({ pressed }) => [
                            authSharedStyles.primaryButton,
                            pressed && authSharedStyles.primaryButtonPressed,
                        ]}
                    >
                        <Text style={authSharedStyles.primaryButtonText}>{t("auth.entry.login")}</Text>
                    </Pressable>

                    <Pressable
                        onPress={() => router.push(ROUTES.register)}
                        style={({ pressed }) => [
                            authSharedStyles.secondaryButton,
                            pressed && authSharedStyles.secondaryButtonPressed,
                        ]}
                    >
                        <Text style={authSharedStyles.secondaryButtonText}>{t("auth.entry.register")}</Text>
                    </Pressable>
                </View>
            </ScrollView>
        </SafeAreaView>
    )
}
