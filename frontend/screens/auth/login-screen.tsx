import { useState } from "react"
import { ActivityIndicator, Pressable, Text, TextInput, View } from "react-native"
import { router } from "expo-router"

import { ROUTES } from "@/constants/routes"
import { useAuth } from "@/providers/auth-provider"
import { useLanguage } from "@/providers/language-provider"
import AuthFormLayout from "@/screens/auth/auth-form-layout"
import { authSharedStyles } from "@/screens/auth/auth-shared.styles"
import EmailVerificationStep from "@/screens/auth/email-verification-step"
import PasswordField from "@/screens/auth/password-field"
import { useAuthFormScroll } from "@/screens/auth/use-auth-form-scroll"

type LoginStep = "credentials" | "verification"

export default function LoginScreen() {
    const { resendLoginCode, signIn, verifyLogin } = useAuth()
    const { t } = useLanguage()
    const { handleFieldLayout, scrollRef, scrollToField } = useAuthFormScroll(["login", "password"] as const)
    const [step, setStep] = useState<LoginStep>("credentials")
    const [login, setLogin] = useState("")
    const [password, setPassword] = useState("")
    const [pendingEmail, setPendingEmail] = useState("")
    const [error, setError] = useState("")
    const [statusMessage, setStatusMessage] = useState("")
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [isResending, setIsResending] = useState(false)

    const handleSubmit = async () => {
        if (!login.trim() || !password.trim()) {
            setError(t("auth.error.loginRequired"))
            return
        }

        setError("")
        setIsSubmitting(true)

        try {
            const result = await signIn({
                login: login.trim(),
                password,
            })
            if (result.verificationRequired) {
                setPendingEmail(result.email)
                setStatusMessage("")
                setStep("verification")
                return
            }
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

    const handleVerify = async (code: string) => {
        if (code.length !== 6) {
            setError(t("auth.error.codeRequired"))
            return false
        }

        setError("")
        setStatusMessage("")
        setIsSubmitting(true)

        try {
            await verifyLogin({
                email: pendingEmail,
                code,
            })
            router.replace(ROUTES.home)
            return true
        } catch (submitError) {
            setError(submitError instanceof Error ? submitError.message : t("auth.error.verifyFallback"))
            return false
        } finally {
            setIsSubmitting(false)
        }
    }

    const handleResend = async () => {
        setError("")
        setStatusMessage("")
        setIsResending(true)

        try {
            const response = await resendLoginCode({ login: login.trim(), password })
            setPendingEmail(response.email)
            setStatusMessage(t("auth.verify.resendSuccess"))
        } catch (resendError) {
            setError(resendError instanceof Error ? resendError.message : t("auth.error.resendCodeFallback"))
        } finally {
            setIsResending(false)
        }
    }

    if (step === "verification") {
        return (
            <AuthFormLayout error={error} scrollRef={scrollRef} title={t("auth.verify.title")}>
                <EmailVerificationStep
                    email={pendingEmail}
                    isChecking={isSubmitting}
                    isResending={isResending}
                    onEditEmail={() => {
                        setStep("credentials")
                        setError("")
                        setStatusMessage("")
                    }}
                    onResend={handleResend}
                    onVerify={handleVerify}
                    statusMessage={statusMessage}
                />
            </AuthFormLayout>
        )
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
