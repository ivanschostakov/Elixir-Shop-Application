import { useState } from "react"
import { ActivityIndicator, Alert, Pressable, Text, TextInput, View } from "react-native"
import { router } from "expo-router"

import { ROUTES } from "@/constants/routes"
import { useAuth } from "@/providers/auth-provider"
import { useLanguage } from "@/providers/language-provider"
import AuthFormLayout from "@/screens/auth/auth-form-layout"
import { authSharedStyles } from "@/screens/auth/auth-shared.styles"
import EmailVerificationStep from "@/screens/auth/email-verification-step"
import PasswordField from "@/screens/auth/password-field"
import { useAuthFormScroll } from "@/screens/auth/use-auth-form-scroll"

type RegistrationStep = "details" | "verification"

export default function RegisterScreen() {
    const { register, resendRegistrationCode, verifyRegistration } = useAuth()
    const { t } = useLanguage()
    const { handleFieldLayout, scrollRef, scrollToField } = useAuthFormScroll(
        ["username", "name", "surname", "email", "password", "confirmPassword"] as const,
    )
    const [step, setStep] = useState<RegistrationStep>("details")
    const [username, setUsername] = useState("")
    const [name, setName] = useState("")
    const [surname, setSurname] = useState("")
    const [email, setEmail] = useState("")
    const [password, setPassword] = useState("")
    const [confirmPassword, setConfirmPassword] = useState("")
    const [pendingEmail, setPendingEmail] = useState("")
    const [error, setError] = useState("")
    const [statusMessage, setStatusMessage] = useState("")
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [isResending, setIsResending] = useState(false)

    const showAuthAlert = (message: string) => {
        Alert.alert(t("auth.error.alertTitle"), message)
    }

    const handleSubmit = async () => {
        if (
            !username.trim() ||
            !name.trim() ||
            !surname.trim() ||
            !email.trim() ||
            !password.trim() ||
            !confirmPassword.trim()
        ) {
            setError(t("auth.error.registerRequired"))
            return
        }

        if (!email.includes("@")) {
            setError(t("auth.error.invalidEmail"))
            return
        }

        if (username.trim().length > 16) {
            setError(t("auth.error.usernameLength"))
            return
        }

        if (password.length < 8) {
            setError(t("auth.error.passwordLength"))
            return
        }

        if (password !== confirmPassword) {
            setError(t("auth.error.passwordMismatch"))
            return
        }

        setError("")
        setIsSubmitting(true)

        try {
            const response = await register({
                username: username.trim(),
                name: name.trim(),
                surname: surname.trim(),
                email: email.trim(),
                password,
            })
            setPendingEmail(response.email)
            setStatusMessage("")
            setStep("verification")
        } catch (submitError) {
            const nextError = submitError instanceof Error ? submitError.message : t("auth.error.registerFallback")
            setError(nextError)
            showAuthAlert(nextError)
        } finally {
            setIsSubmitting(false)
        }
    }

    const handleVerify = async (code: string) => {
        if (code.length !== 6) {
            const nextError = t("auth.error.codeRequired")
            setError(nextError)
            showAuthAlert(nextError)
            return false
        }

        setError("")
        setStatusMessage("")
        setIsSubmitting(true)

        try {
            await verifyRegistration({
                email: pendingEmail,
                code,
            })
            router.replace(ROUTES.discover)
            return true
        } catch (submitError) {
            const nextError = submitError instanceof Error ? submitError.message : t("auth.error.verifyFallback")
            setError(nextError)
            showAuthAlert(nextError)
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
            await resendRegistrationCode({ email: pendingEmail })
            setStatusMessage(t("auth.verify.resendSuccess"))
        } catch (resendError) {
            const nextError = resendError instanceof Error ? resendError.message : t("auth.error.resendCodeFallback")
            setError(nextError)
            showAuthAlert(nextError)
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
                        setStep("details")
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
        <AuthFormLayout error={error} scrollRef={scrollRef} title={t("auth.register.title")}>
            <View onLayout={handleFieldLayout("username")} style={authSharedStyles.formGroup}>
                <Text style={authSharedStyles.fieldLabel}>{t("auth.register.username")}</Text>
                <TextInput
                    autoCapitalize="none"
                    autoCorrect={false}
                    onChangeText={setUsername}
                    onFocus={() => scrollToField("username")}
                    placeholder={t("auth.register.usernamePlaceholder")}
                    returnKeyType="next"
                    style={authSharedStyles.input}
                    value={username}
                />
            </View>

            <View onLayout={handleFieldLayout("name")} style={authSharedStyles.formGroup}>
                <Text style={authSharedStyles.fieldLabel}>{t("auth.register.name")}</Text>
                <TextInput
                    onChangeText={setName}
                    onFocus={() => scrollToField("name")}
                    placeholder={t("auth.register.namePlaceholder")}
                    returnKeyType="next"
                    style={authSharedStyles.input}
                    value={name}
                />
            </View>

            <View onLayout={handleFieldLayout("surname")} style={authSharedStyles.formGroup}>
                <Text style={authSharedStyles.fieldLabel}>{t("auth.register.surname")}</Text>
                <TextInput
                    onChangeText={setSurname}
                    onFocus={() => scrollToField("surname")}
                    placeholder={t("auth.register.surnamePlaceholder")}
                    returnKeyType="next"
                    style={authSharedStyles.input}
                    value={surname}
                />
            </View>

            <View onLayout={handleFieldLayout("email")} style={authSharedStyles.formGroup}>
                <Text style={authSharedStyles.fieldLabel}>{t("auth.register.email")}</Text>
                <TextInput
                    autoCapitalize="none"
                    autoCorrect={false}
                    keyboardType="email-address"
                    onChangeText={setEmail}
                    onFocus={() => scrollToField("email")}
                    placeholder="name@example.com"
                    returnKeyType="next"
                    style={authSharedStyles.input}
                    value={email}
                />
            </View>

            <View onLayout={handleFieldLayout("password")} style={authSharedStyles.formGroup}>
                <PasswordField
                    label={t("auth.register.password")}
                    onChangeText={setPassword}
                    onFocus={() => scrollToField("password")}
                    placeholder={t("auth.register.passwordPlaceholder")}
                    returnKeyType="next"
                    value={password}
                />
            </View>

            <View onLayout={handleFieldLayout("confirmPassword")} style={authSharedStyles.formGroup}>
                <PasswordField
                    label={t("auth.register.confirmPassword")}
                    onChangeText={setConfirmPassword}
                    onFocus={() => scrollToField("confirmPassword")}
                    placeholder={t("auth.register.confirmPasswordPlaceholder")}
                    returnKeyType="done"
                    value={confirmPassword}
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
                    <Text style={authSharedStyles.primaryButtonText}>{t("auth.register.submit")}</Text>
                )}
            </Pressable>

            <View style={authSharedStyles.helperRow}>
                <Text style={authSharedStyles.helperText}>{t("auth.register.haveAccount")}</Text>
                <Pressable onPress={() => router.push(ROUTES.login)}>
                    <Text style={authSharedStyles.helperLink}>{t("auth.register.goToLogin")}</Text>
                </Pressable>
            </View>
        </AuthFormLayout>
    )
}
