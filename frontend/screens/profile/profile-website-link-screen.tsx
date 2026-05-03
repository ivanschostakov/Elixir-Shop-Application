import { useState } from "react"
import { ActivityIndicator, Alert, Pressable, Text, TextInput, View } from "react-native"
import { router } from "expo-router"

import { useLanguage } from "@/providers/language-provider"
import AuthFormLayout from "@/screens/auth/auth-form-layout"
import { authSharedStyles } from "@/screens/auth/auth-shared.styles"
import PasswordField from "@/screens/auth/password-field"
import { getErrorMessage } from "@/screens/profile/profile-website-link-screen.utils"
import { linkMyWebsiteIdentity } from "@/services/api/website-identity"
import { isBackendError, showBackendErrorAlert } from "@/utils/errors"

export default function ProfileWebsiteLinkScreen() {
    const { t } = useLanguage()
    const [login, setLogin] = useState("")
    const [password, setPassword] = useState("")
    const [error, setError] = useState("")
    const [isSubmitting, setIsSubmitting] = useState(false)

    const handleSubmit = async () => {
        if (!login.trim() || !password.trim()) {
            setError(t("profile.website.requiredCredentials"))
            return
        }

        setError("")
        setIsSubmitting(true)

        try {
            await linkMyWebsiteIdentity({
                login: login.trim(),
                password,
            })
            router.back()
        } catch (submitError) {
            const message = getErrorMessage(submitError, t("profile.website.linkFallback"))
            setError(message)
            showBackendErrorAlert(submitError, message)
            if (!isBackendError(submitError)) {
                Alert.alert(t("auth.error.alertTitle"), message)
            }
        } finally {
            setIsSubmitting(false)
        }
    }

    return (
        <AuthFormLayout error={error} title={t("profile.website.connectTitle")}>
            <Text style={authSharedStyles.helperText}>{t("profile.website.connectScreenSubtitle")}</Text>

            <View style={authSharedStyles.formGroup}>
                <Text style={authSharedStyles.fieldLabel}>{t("profile.website.loginField")}</Text>
                <TextInput
                    autoCapitalize="none"
                    autoCorrect={false}
                    onChangeText={setLogin}
                    placeholder={t("profile.website.loginPlaceholder")}
                    returnKeyType="next"
                    style={authSharedStyles.input}
                    value={login}
                />
            </View>

            <View style={authSharedStyles.formGroup}>
                <PasswordField
                    label={t("profile.website.passwordField")}
                    onChangeText={setPassword}
                    placeholder={t("profile.website.passwordPlaceholder")}
                    returnKeyType="done"
                    value={password}
                />
            </View>

            <Pressable
                disabled={isSubmitting}
                onPress={handleSubmit}
                style={({ pressed }) => [
                    authSharedStyles.primaryButton,
                    (pressed || isSubmitting) && authSharedStyles.primaryButtonPressed,
                ]}
            >
                {isSubmitting ? (
                    <ActivityIndicator color="#ffffff" />
                ) : (
                    <Text style={authSharedStyles.primaryButtonText}>{t("profile.website.connectAction")}</Text>
                )}
            </Pressable>
        </AuthFormLayout>
    )
}
