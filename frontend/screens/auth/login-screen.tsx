import { useState } from "react"
import { ActivityIndicator, Pressable, Text, TextInput, View } from "react-native"
import { router } from "expo-router"

import { ROUTES } from "@/constants/routes"
import { useAuth } from "@/providers/auth-provider"
import { useLanguage } from "@/providers/language-provider"
import AuthFormLayout from "@/screens/auth/auth-form-layout"
import { authSharedStyles } from "@/screens/auth/auth-shared.styles"
import PasswordField from "@/screens/auth/password-field"
import { useAuthFormScroll } from "@/screens/auth/use-auth-form-scroll"

export default function LoginScreen() {
    const { signIn } = useAuth()
    const { t } = useLanguage()
    const { handleFieldLayout, scrollRef, scrollToField } = useAuthFormScroll(["login", "password"] as const)
    const [login, setLogin] = useState("")
    const [password, setPassword] = useState("")
    const [error, setError] = useState("")
    const [isSubmitting, setIsSubmitting] = useState(false)

    const handleSubmit = async () => {
        if (!login.trim() || !password.trim()) {
            setError(t("auth.error.loginRequired"))
            return
        }

        setError("")
        setIsSubmitting(true)

        try {
            await signIn({
                login,
                password,
            })
            router.replace(ROUTES.home)
        } catch (submitError) {
            setError(
                submitError instanceof Error
                    ? submitError.message
                    : t("auth.error.loginFallback"),
            )
        } finally {
            setIsSubmitting(false)
        }
    }

    return (
        <AuthFormLayout error={error} scrollRef={scrollRef} title={t("auth.login.title")}>
            <View onLayout={handleFieldLayout("login")} style={authSharedStyles.formGroup}>
                <Text style={authSharedStyles.fieldLabel}>{t("auth.login.loginOrEmail")}</Text>
                <TextInput
                    autoCapitalize="none"
                    autoCorrect={false}
                    onChangeText={setLogin}
                    onFocus={() => scrollToField("login")}
                    placeholder={t("auth.login.loginOrEmailPlaceholder")}
                    returnKeyType="next"
                    style={authSharedStyles.input}
                    value={login}
                />
            </View>

            <View onLayout={handleFieldLayout("password")} style={authSharedStyles.formGroup}>
                <PasswordField
                    label={t("auth.register.password")}
                    onChangeText={setPassword}
                    onFocus={() => scrollToField("password")}
                    placeholder={t("auth.login.passwordPlaceholder")}
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
                    <Text style={authSharedStyles.primaryButtonText}>{t("auth.login.submit")}</Text>
                )}
            </Pressable>

            <Pressable
                onPress={() => router.push(ROUTES.register)}
                style={({ pressed }) => [
                    authSharedStyles.secondaryButton,
                    pressed && authSharedStyles.secondaryButtonPressed,
                ]}
            >
                <Text style={authSharedStyles.secondaryButtonText}>{t("auth.login.goToRegister")}</Text>
            </Pressable>
        </AuthFormLayout>
    )
}
