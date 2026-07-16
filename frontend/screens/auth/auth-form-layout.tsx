import { KeyboardAvoidingView, Platform, ScrollView, Text, View } from "react-native"
import { SafeAreaView } from "react-native-safe-area-context"

import { createAuthSharedStyles } from "@/screens/auth/auth-shared.styles"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import type { AuthFormLayoutProps } from "@/screens/auth/auth-form-layout.types"

export default function AuthFormLayout({ children, error, scrollRef, title }: AuthFormLayoutProps) {
    const authSharedStyles = useThemeStyles(createAuthSharedStyles)
    return (
        <KeyboardAvoidingView
            behavior={Platform.OS === "ios" ? "padding" : "height"}
            style={authSharedStyles.keyboard}
        >
            <SafeAreaView style={authSharedStyles.container}>
                <ScrollView
                    contentContainerStyle={authSharedStyles.content}
                    keyboardShouldPersistTaps="handled"
                    ref={scrollRef}
                >
                    <View style={authSharedStyles.card}>
                        <Text style={authSharedStyles.title}>{title}</Text>

                        {error ? (
                            <View style={authSharedStyles.errorBox}>
                                <Text style={authSharedStyles.errorText}>{error}</Text>
                            </View>
                        ) : null}

                        {children}
                    </View>
                </ScrollView>
            </SafeAreaView>
        </KeyboardAvoidingView>
    )
}
