import { KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, View } from "react-native"
import { SafeAreaView } from "react-native-safe-area-context"
import { Path, Svg } from "react-native-svg"

import { BACK_ARROW_PATH } from "@/components/header/app-header.constants"
import { createAuthSharedStyles } from "@/screens/auth/auth-shared.styles"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import type { AuthFormLayoutProps } from "@/screens/auth/auth-form-layout.types"
import { useTheme } from "@/providers/theme-provider"

export default function AuthFormLayout({ backAction, children, error, scrollRef, title }: AuthFormLayoutProps) {
    const authSharedStyles = useThemeStyles(createAuthSharedStyles)
    const { palette } = useTheme()
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
                        {backAction ? (
                            <View style={authSharedStyles.verificationHeader}>
                                <Pressable
                                    accessibilityLabel={backAction.label}
                                    accessibilityRole="button"
                                    disabled={backAction.disabled}
                                    onPress={backAction.onPress}
                                    style={({ pressed }) => [authSharedStyles.headerBackButton, pressed && authSharedStyles.verificationBackButtonPressed]}
                                >
                                    <Svg width={24} height={24} viewBox="0 0 24 24" fill="none">
                                        <Path d={BACK_ARROW_PATH} fill={palette.text} />
                                    </Svg>
                                </Pressable>
                                <Text accessibilityRole="header" style={[authSharedStyles.title, authSharedStyles.verificationHeaderTitle]}>{title}</Text>
                            </View>
                        ) : <Text style={authSharedStyles.title}>{title}</Text>}

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
