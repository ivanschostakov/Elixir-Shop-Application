import { useRef, useState } from "react"
import { ActivityIndicator, Keyboard, Pressable, Text, TextInput, View } from "react-native"

import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useLanguage } from "@/providers/language-provider"
import AuthFormLayout from "@/screens/auth/auth-form-layout"
import { createAuthSharedStyles } from "@/screens/auth/auth-shared.styles"
import EmailVerificationStep from "@/screens/auth/email-verification-step"
import PasswordField from "@/screens/auth/password-field"
import { useAuthFormScroll } from "@/screens/auth/use-auth-form-scroll"
import { ApiError } from "@/services/api/client"
import { completePasswordReset, confirmPasswordReset, getAuthErrorMessage, requestPasswordReset, verifyPasswordReset } from "@/services/auth/auth"

type Props = {
    initialEmail: string
    onBack: () => void
    onSuccess: (email: string) => void
}

export default function PasswordResetScreen({ initialEmail, onBack, onSuccess }: Props) {
    const { t } = useLanguage()
    const styles = useThemeStyles(createAuthSharedStyles)
    const { handleFieldLayout, scrollRef, scrollToField } = useAuthFormScroll(["email", "code", "password", "repeat"] as const)
    const [email, setEmail] = useState(initialEmail)
    const [code, setCode] = useState("")
    const [password, setPassword] = useState("")
    const [repeat, setRepeat] = useState("")
    const [sent, setSent] = useState(false)
    const [busy, setBusy] = useState(false)
    const [error, setError] = useState("")
    const [resetToken, setResetToken] = useState<string | null>(null)
    const [legacyRecovery, setLegacyRecovery] = useState(false)
    const [resending, setResending] = useState(false)
    const [statusMessage, setStatusMessage] = useState("")
    const inFlight = useRef(false)
    const address = email.trim()

    const runRequest = async (action: () => Promise<void>, resend = false) => {
        if (inFlight.current) return false
        inFlight.current = true
        setBusy(true)
        setResending(resend)
        setError("")
        setStatusMessage("")
        try {
            await action()
            return true
        } catch (failure) {
            setError(failure instanceof ApiError && failure.status === 429
                ? t("auth.reset.rateLimited")
                : getAuthErrorMessage(failure, t("auth.reset.failed")))
            if (resetToken && failure instanceof ApiError && failure.status === 400) {
                setResetToken(null)
                setPassword("")
                setRepeat("")
            }
            return false
        } finally {
            inFlight.current = false
            setBusy(false)
            setResending(false)
        }
    }

    const editEmail = () => {
        if (inFlight.current) return
        setSent(false)
        setCode("")
        setResetToken(null)
        setPassword("")
        setRepeat("")
        setError("")
        setStatusMessage("")
    }

    const submit = async (resend = false) => {
        if (inFlight.current) return
        const confirm = sent && !resend
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(address)) return setError(t("auth.reset.emailRequired"))
        if (confirm) {
            if (!resetToken && !/^[0-9]{6}$/.test(code)) return setError(t("auth.error.codeRequired"))
            if (!password.trim() || [...password].length < 8) return setError(t("auth.error.passwordLength"))
            if ([...password].length > 100) return setError(t("auth.reset.passwordTooLong"))
            if (password !== repeat) return setError(t("auth.error.passwordMismatch"))
        }
        await runRequest(async () => {
            if (confirm) {
                if (resetToken) await completePasswordReset(address, resetToken, password)
                else await confirmPasswordReset(address, code, password)
                onSuccess(address)
            } else {
                await requestPasswordReset(address)
                setCode("")
                setSent(true)
                if (resend) setStatusMessage(t("auth.verify.resendSuccess"))
            }
        }, resend)
    }

    const passwordFields = (
        <>
            <View onLayout={handleFieldLayout("password")} style={styles.formGroup}>
                <PasswordField
                    label={t("auth.reset.newPassword")}
                    onChangeText={setPassword}
                    onFocus={() => scrollToField("password")}
                    placeholder={t("auth.register.passwordPlaceholder")}
                    value={password}
                />
            </View>
            <View onLayout={handleFieldLayout("repeat")} style={styles.formGroup}>
                <PasswordField
                    label={t("auth.register.confirmPassword")}
                    onChangeText={setRepeat}
                    onFocus={() => scrollToField("repeat")}
                    placeholder={t("auth.register.confirmPasswordPlaceholder")}
                    value={repeat}
                />
            </View>
        </>
    )
    const submitButton = (
        <Pressable accessibilityRole="button" disabled={busy} onPress={() => void submit()} style={styles.primaryButton}>
            {busy ? <ActivityIndicator color="#ffffff" /> : (
                <Text style={styles.primaryButtonText}>{t(sent ? "auth.reset.save" : "auth.reset.send")}</Text>
            )}
        </Pressable>
    )

    if (sent && !legacyRecovery) {
        const backAction = { label: t("nav.back"), onPress: editEmail, disabled: busy }
        return resetToken ? (
            <AuthFormLayout key="password" backAction={backAction} error={error} scrollRef={scrollRef} title={t("auth.reset.newPassword")}>
                {passwordFields}
                {submitButton}
            </AuthFormLayout>
        ) : (
            <AuthFormLayout key="code" backAction={backAction} error={error} scrollRef={scrollRef} title={t("auth.verify.title")}>
                <EmailVerificationStep
                    email={address}
                    headerBack
                    isChecking={busy && !resending}
                    isResending={resending}
                    onEditEmail={editEmail}
                    onResend={() => submit(true)}
                    onVerify={(value) => runRequest(async () => {
                        try {
                            const token = await verifyPasswordReset(address, value)
                            Keyboard.dismiss()
                            setResetToken(token)
                        } catch (failure) {
                            if (!(failure instanceof ApiError) || failure.status !== 404) throw failure
                            setCode(value)
                            setLegacyRecovery(true)
                        }
                    })}
                    statusMessage={statusMessage}
                />
            </AuthFormLayout>
        )
    }

    return (
        <AuthFormLayout error={error} scrollRef={scrollRef} title={t("auth.reset.title")}>
            <View onLayout={handleFieldLayout("email")} style={styles.formGroup}>
                <Text style={styles.fieldLabel}>{t("auth.register.email")}</Text>
                <TextInput
                    accessibilityLabel={t("auth.register.email")}
                    autoCapitalize="none"
                    autoComplete="email"
                    autoCorrect={false}
                    editable={!sent && !busy}
                    keyboardType="email-address"
                    maxLength={100}
                    onChangeText={setEmail}
                    onFocus={() => scrollToField("email")}
                    style={styles.input}
                    value={email}
                />
            </View>
            {sent ? (
                <>
                    <Text style={styles.helperText}>{t("auth.reset.sent")}</Text>
                    <View onLayout={handleFieldLayout("code")} style={styles.formGroup}>
                        <Text style={styles.fieldLabel}>{t("auth.verify.code")}</Text>
                        <TextInput
                            accessibilityLabel={t("auth.verify.code")}
                            autoComplete="one-time-code"
                            keyboardType="number-pad"
                            maxLength={6}
                            onChangeText={(value) => setCode(value.replace(/[^0-9]/g, ""))}
                            onFocus={() => scrollToField("code")}
                            style={styles.input}
                            textContentType="oneTimeCode"
                            value={code}
                        />
                    </View>
                    {passwordFields}
                </>
            ) : null}
            {submitButton}
            {sent ? (
                <View style={[styles.helperRow, { flexWrap: "wrap" }]}>
                    <Pressable accessibilityRole="button" disabled={busy} onPress={() => void submit(true)}>
                        <Text style={styles.helperLink}>{t("auth.verify.resend")}</Text>
                    </Pressable>
                    <Text style={styles.helperText}>·</Text>
                    <Pressable accessibilityRole="button" disabled={busy} onPress={editEmail}>
                        <Text style={styles.helperLink}>{t("auth.reset.changeEmail")}</Text>
                    </Pressable>
                </View>
            ) : null}
            <Pressable accessibilityRole="button" disabled={busy} onPress={onBack} style={styles.secondaryButton}>
                <Text style={styles.secondaryButtonText}>{t("auth.reset.back")}</Text>
            </Pressable>
        </AuthFormLayout>
    )
}
