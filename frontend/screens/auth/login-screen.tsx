import { useState } from "react"
import { ActivityIndicator, Alert, Pressable, Text, TextInput, View } from "react-native"
import { router } from "expo-router"

import { ROUTES } from "@/constants/routes"
import { useAuth } from "@/providers/auth-provider"
import { useLanguage } from "@/providers/language-provider"
import AuthFormLayout from "@/screens/auth/auth-form-layout"
import { createAuthSharedStyles } from "@/screens/auth/auth-shared.styles"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import EmailVerificationStep from "@/screens/auth/email-verification-step"
import PasswordField from "@/screens/auth/password-field"
import { useAuthFormScroll } from "@/screens/auth/use-auth-form-scroll"
import type { PhoneAuthStartStep } from "@/services/auth/auth.types"

type AuthStep = "phone" | "login" | "claim" | "register" | "verification"

export default function LoginScreen() {
    const authSharedStyles = useThemeStyles(createAuthSharedStyles)
    const {
        acceptSession,
        claimPhoneAccount,
        registerPhoneAccount,
        resendPhoneAuthCode,
        signIn,
        startPhoneAuth,
        verifyPhoneAuth,
    } = useAuth()
    const { t } = useLanguage()
    const { handleFieldLayout, scrollRef, scrollToField } = useAuthFormScroll(
        ["phoneNumber", "name", "surname", "email", "password", "confirmPassword"] as const,
    )
    const [step, setStep] = useState<AuthStep>("phone")
    const [verificationReturnStep, setVerificationReturnStep] = useState<AuthStep>("phone")
    const [phoneNumber, setPhoneNumber] = useState("")
    const [email, setEmail] = useState("")
    const [emailHint, setEmailHint] = useState("")
    const [name, setName] = useState("")
    const [surname, setSurname] = useState("")
    const [password, setPassword] = useState("")
    const [confirmPassword, setConfirmPassword] = useState("")
    const [pendingEmail, setPendingEmail] = useState<string | null>(null)
    const [error, setError] = useState("")
    const [statusMessage, setStatusMessage] = useState("")
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [isResending, setIsResending] = useState(false)

    const showAuthAlert = (message: string) => {
        Alert.alert(t("auth.error.alertTitle"), message)
    }

    const resetAuthMessages = () => {
        setError("")
        setStatusMessage("")
    }

    const completeSetupResponse = (response: Awaited<ReturnType<typeof claimPhoneAccount>>) => {
        if ("user" in response) {
            acceptSession(response)
            router.replace(ROUTES.discover)
            return true
        }

        setPendingEmail(response.email)
        return false
    }

    const handleStart = async () => {
        if (!phoneNumber.trim()) {
            setError(t("auth.error.phoneRequired"))
            return
        }

        resetAuthMessages()
        setIsSubmitting(true)

        try {
            const response = await startPhoneAuth({ phone_number: phoneNumber.trim() })
            setEmailHint(response.email_hint ?? "")
            setStatusMessage("")

            const nextStepByFlow: Record<PhoneAuthStartStep, AuthStep> = {
                login: "login",
                claim: "claim",
                register: "register",
            }
            setStep(nextStepByFlow[response.next_step])
        } catch (submitError) {
            const nextError = submitError instanceof Error ? submitError.message : t("auth.error.loginFallback")
            setError(nextError)
            showAuthAlert(nextError)
        } finally {
            setIsSubmitting(false)
        }
    }

    const handleLogin = async () => {
        if (!password.trim()) {
            setError(t("auth.error.loginRequired"))
            return
        }

        resetAuthMessages()
        setIsSubmitting(true)

        try {
            await signIn({
                phone_number: phoneNumber.trim(),
                password,
            })
            router.replace(ROUTES.discover)
        } catch (submitError) {
            const nextError = submitError instanceof Error ? submitError.message : t("auth.error.loginFallback")
            setError(nextError)
            showAuthAlert(nextError)
        } finally {
            setIsSubmitting(false)
        }
    }

    const validatePasswordPair = () => {
        if (!password.trim() || !confirmPassword.trim()) {
            setError(t("auth.error.registerRequired"))
            return false
        }
        if (password.length < 8) {
            setError(t("auth.error.passwordLength"))
            return false
        }
        if (password !== confirmPassword) {
            setError(t("auth.error.passwordMismatch"))
            return false
        }
        return true
    }

    const handleClaim = async () => {
        if (email.trim() && !email.includes("@")) {
            setError(t("auth.error.invalidEmail"))
            return
        }
        if (!validatePasswordPair()) {
            return
        }

        resetAuthMessages()
        setIsSubmitting(true)

        try {
            const response = await claimPhoneAccount({
                phone_number: phoneNumber.trim(),
                password,
                email: email.trim() || undefined,
            })
            if (!completeSetupResponse(response)) {
                setVerificationReturnStep("claim")
                setStep("verification")
            }
        } catch (submitError) {
            const nextError = submitError instanceof Error ? submitError.message : t("auth.error.registerFallback")
            setError(nextError)
            showAuthAlert(nextError)
        } finally {
            setIsSubmitting(false)
        }
    }

    const handleRegister = async () => {
        if (!name.trim() || !surname.trim()) {
            setError(t("auth.error.registerRequired"))
            return
        }
        if (email.trim() && !email.includes("@")) {
            setError(t("auth.error.invalidEmail"))
            return
        }
        if (!validatePasswordPair()) {
            return
        }

        resetAuthMessages()
        setIsSubmitting(true)

        try {
            const response = await registerPhoneAccount({
                phone_number: phoneNumber.trim(),
                name: name.trim(),
                surname: surname.trim(),
                email: email.trim() || undefined,
                password,
            })
            if (!completeSetupResponse(response)) {
                setVerificationReturnStep("register")
                setStep("verification")
            }
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

        resetAuthMessages()
        setIsSubmitting(true)

        try {
            await verifyPhoneAuth({
                phone_number: phoneNumber.trim(),
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
        resetAuthMessages()
        setIsResending(true)

        try {
            await resendPhoneAuthCode({ phone_number: phoneNumber.trim() })
            setStatusMessage(t("auth.verify.resendSuccess"))
        } catch (resendError) {
            const nextError = resendError instanceof Error ? resendError.message : t("auth.error.resendCodeFallback")
            setError(nextError)
            showAuthAlert(nextError)
        } finally {
            setIsResending(false)
        }
    }

    const renderPrimaryButton = (label: string, onPress: () => Promise<void> | void) => (
        <Pressable
            disabled={isSubmitting}
            onPress={() => void onPress()}
            style={({ pressed }) => [
                authSharedStyles.primaryButton,
                (pressed || isSubmitting) && authSharedStyles.primaryButtonPressed,
            ]}
        >
            {isSubmitting ? (
                <ActivityIndicator color="#ffffff" />
            ) : (
                <Text style={authSharedStyles.primaryButtonText}>{label}</Text>
            )}
        </Pressable>
    )

    const renderPhoneField = () => (
        <View onLayout={handleFieldLayout("phoneNumber")} style={authSharedStyles.formGroup}>
            <Text style={authSharedStyles.fieldLabel}>{t("auth.login.username")}</Text>
            <TextInput
                keyboardType="phone-pad"
                onChangeText={setPhoneNumber}
                onFocus={() => scrollToField("phoneNumber")}
                placeholder={t("auth.login.usernamePlaceholder")}
                returnKeyType="next"
                style={authSharedStyles.input}
                textContentType="telephoneNumber"
                value={phoneNumber}
            />
        </View>
    )

    const renderChangePhoneLink = () => (
        <Pressable
            onPress={() => {
                setStep("phone")
                resetAuthMessages()
            }}
            style={({ pressed }) => [pressed && authSharedStyles.textLinkDisabled]}
        >
            <Text style={authSharedStyles.helperLink}>{t("auth.phone.change")}</Text>
        </Pressable>
    )

    if (step === "verification") {
        return (
            <AuthFormLayout error={error} scrollRef={scrollRef} title={t("auth.verify.title")}>
                <EmailVerificationStep
                    email={pendingEmail}
                    isChecking={isSubmitting}
                    isResending={isResending}
                    onEditEmail={() => {
                        setStep(verificationReturnStep)
                        resetAuthMessages()
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
            {step === "phone" ? (
                <>
                    {renderPhoneField()}
                    {renderPrimaryButton(t("auth.phone.submit"), handleStart)}
                </>
            ) : null}

            {step === "login" ? (
                <>
                    {renderPhoneField()}
                    <View style={authSharedStyles.helperRow}>
                        <Text style={authSharedStyles.helperText}>{phoneNumber.trim()}</Text>
                        {renderChangePhoneLink()}
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
                    {renderPrimaryButton(t("auth.login.submit"), handleLogin)}
                </>
            ) : null}

            {step === "claim" ? (
                <>
                    {renderPhoneField()}
                    <View style={authSharedStyles.helperRow}>
                        <Text style={authSharedStyles.helperText}>
                            {emailHint ? `${t("auth.verify.description")} ${emailHint}.` : t("auth.claim.missingEmail")}
                        </Text>
                    </View>
                    {renderChangePhoneLink()}
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
                    {renderPrimaryButton(t("auth.register.submit"), handleClaim)}
                </>
            ) : null}

            {step === "register" ? (
                <>
                    {renderPhoneField()}
                    {renderChangePhoneLink()}
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
                    {renderPrimaryButton(t("auth.register.submit"), handleRegister)}
                </>
            ) : null}

            <View style={authSharedStyles.helperRow}>
                <Pressable
                    onPress={() => router.replace(ROUTES.discover)}
                    style={({ pressed }) => [pressed && authSharedStyles.textLinkDisabled]}
                >
                    <Text style={authSharedStyles.helperLink}>{t("auth.continueAsGuest")}</Text>
                </Pressable>
            </View>
        </AuthFormLayout>
    )
}
