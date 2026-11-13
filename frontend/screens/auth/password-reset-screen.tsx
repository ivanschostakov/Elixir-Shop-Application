import { useRef, useState } from "react"
import { ActivityIndicator, Pressable, Text, TextInput, View } from "react-native"

import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useLanguage } from "@/providers/language-provider"
import AuthFormLayout from "@/screens/auth/auth-form-layout"
import { createAuthSharedStyles } from "@/screens/auth/auth-shared.styles"
import PasswordField from "@/screens/auth/password-field"
import { useAuthFormScroll } from "@/screens/auth/use-auth-form-scroll"
import { ApiError } from "@/services/api/client"
import { confirmPasswordReset, getAuthErrorMessage, requestPasswordReset } from "@/services/auth/auth"

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
    const inFlight = useRef(false)
    const address = email.trim()

    const submit = async (resend = false) => {
        if (inFlight.current) return
        const confirm = sent && !resend
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(address)) return setError(t("auth.reset.emailRequired"))
        if (confirm) {
            if (!/^[0-9]{6}$/.test(code)) return setError(t("auth.error.codeRequired"))
            if (!password.trim() || [...password].length < 8) return setError(t("auth.error.passwordLength"))
            if ([...password].length > 100) return setError(t("auth.reset.passwordTooLong"))
            if (password !== repeat) return setError(t("auth.error.passwordMismatch"))
        }
        inFlight.current = true
        setBusy(true)
        setError("")
        try {
            if (confirm) {
                await confirmPasswordReset(address, code, password)
                onSuccess(address)
            } else {
                await requestPasswordReset(address)
                setCode("")
                setSent(true)
            }
        } catch (failure) {
            setError(failure instanceof ApiError && failure.status === 429
                ? t("auth.reset.rateLimited")
                : getAuthErrorMessage(failure, t("auth.reset.failed")))
        } finally {
            inFlight.current = false
            setBusy(false)
        }
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
            ) : null}
            <Pressable accessibilityRole="button" disabled={busy} onPress={() => void submit()} style={styles.primaryButton}>
                {busy ? <ActivityIndicator color="#ffffff" /> : (
                    <Text style={styles.primaryButtonText}>{t(sent ? "auth.reset.save" : "auth.reset.send")}</Text>
                )}
            </Pressable>
            {sent ? (
                <View style={[styles.helperRow, { flexWrap: "wrap" }]}>
                    <Pressable accessibilityRole="button" disabled={busy} onPress={() => void submit(true)}>
                        <Text style={styles.helperLink}>{t("auth.verify.resend")}</Text>
                    </Pressable>
                    <Text style={styles.helperText}>·</Text>
                    <Pressable accessibilityRole="button" disabled={busy} onPress={() => {
                        setSent(false)
                        setCode("")
                        setPassword("")
                        setRepeat("")
                        setError("")
                    }}>
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
