import { useEffect, useRef, useState } from "react"
import { ActivityIndicator, Pressable, Text, TextInput, View } from "react-native"
import { Path, Svg } from "react-native-svg"

import { BACK_ARROW_PATH } from "@/components/header/app-header.constants"
import { useLanguage } from "@/providers/language-provider"
import { createAuthSharedStyles } from "@/screens/auth/auth-shared.styles"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useTheme } from "@/providers/theme-provider"
import type { EmailVerificationStepProps } from "@/screens/auth/email-verification-step.types"

export default function EmailVerificationStep({
    email,
    isChecking,
    isResending,
    onEditEmail,
    onResend,
    onVerify,
    statusMessage,
    headerBack = false,
}: EmailVerificationStepProps) {
    const authSharedStyles = useThemeStyles(createAuthSharedStyles)
    const { palette } = useTheme()
    const { t } = useLanguage()
    const [verificationCode, setVerificationCode] = useState("")
    const verificationInputRef = useRef<TextInput>(null)
    const verifying = useRef(false)
    const resending = useRef(false)

    useEffect(() => {
        const focusTimeout = setTimeout(() => {
            verificationInputRef.current?.focus()
        }, 150)

        return () => clearTimeout(focusTimeout)
    }, [email])

    const handleCodeChange = (value: string) => {
        const nextCode = value.replace(/\D/g, "").slice(0, 6)
        setVerificationCode(nextCode)

        if (nextCode.length === 6 && !isChecking && !verifying.current && !resending.current) {
            void handleVerify(nextCode)
        }
    }

    const handleVerify = async (code: string) => {
        verifying.current = true
        let verified = false
        try {
            verified = await onVerify(code)
        } finally {
            verifying.current = false
        }

        if (!verified) {
            setVerificationCode("")
            requestAnimationFrame(() => verificationInputRef.current?.focus())
        }
    }

    const codeDigits = Array.from({ length: 6 }, (_, index) => verificationCode[index] ?? "")

    return (
        <View style={authSharedStyles.verificationStep}>
            {!headerBack ? <Pressable
                accessibilityLabel={t("auth.verify.editEmail")}
                accessibilityRole="button"
                hitSlop={10}
                onPress={onEditEmail}
                style={({ pressed }) => [
                    authSharedStyles.verificationBackButton,
                    pressed ? authSharedStyles.verificationBackButtonPressed : null,
                ]}
            >
                <Svg width={24} height={24} viewBox="0 0 24 24" fill="none">
                    <Path d={BACK_ARROW_PATH} fill={palette.text} />
                </Svg>
            </Pressable> : null}

            <View style={[authSharedStyles.verificationPanel, headerBack && authSharedStyles.verificationPanelWithHeader]}>
                <Text style={authSharedStyles.verificationText}>
                    {t("auth.verify.description")}
                    {email ? (
                        <>
                            {" "}
                            <Text style={authSharedStyles.verificationEmail}>{email}</Text>.
                        </>
                    ) : null}
                </Text>

                {statusMessage ? (
                    <View style={authSharedStyles.infoBox}>
                        <Text style={authSharedStyles.infoText}>{statusMessage}</Text>
                    </View>
                ) : null}

                <View style={authSharedStyles.verificationCodeGroup}>
                    <Pressable
                        accessibilityLabel={t("auth.verify.code")}
                        accessibilityRole="button"
                        onPress={() => verificationInputRef.current?.focus()}
                        style={[authSharedStyles.codeCells, headerBack && authSharedStyles.codeCellsWithHeader]}
                    >
                        {codeDigits.map((digit, index) => (
                            <View
                                key={index}
                                style={[
                                    authSharedStyles.codeCell,
                                    headerBack && authSharedStyles.codeCellWithHeader,
                                    digit ? authSharedStyles.codeCellFilled : null,
                                    verificationCode.length === index ? authSharedStyles.codeCellActive : null,
                                ]}
                            >
                                <Text style={authSharedStyles.codeCellText}>{digit}</Text>
                            </View>
                        ))}
                    </Pressable>
                    <TextInput
                        ref={verificationInputRef}
                        autoCapitalize="none"
                        autoCorrect={false}
                        caretHidden
                        editable={!headerBack || (!isChecking && !isResending)}
                        keyboardType="number-pad"
                        maxLength={6}
                        onChangeText={handleCodeChange}
                        returnKeyType="done"
                        style={authSharedStyles.hiddenCodeInput}
                        textContentType="oneTimeCode"
                        value={verificationCode}
                    />
                </View>

                {isChecking ? (
                    <View style={authSharedStyles.verificationCheckingRow}>
                        <ActivityIndicator color={palette.primary} />
                        <Text style={authSharedStyles.verificationCheckingText}>{t("auth.verify.checking")}</Text>
                    </View>
                ) : null}

                <View style={[authSharedStyles.helperRow, headerBack && authSharedStyles.verificationResendRow]}>
                    <Text style={authSharedStyles.helperText}>{t("auth.verify.resendHint")}</Text>
                    <Pressable disabled={isResending || isChecking} onPress={() => {
                        if (verifying.current || resending.current) return
                        resending.current = true
                        void onResend().finally(() => {
                            resending.current = false
                            if (headerBack) {
                                setVerificationCode("")
                                requestAnimationFrame(() => verificationInputRef.current?.focus())
                            }
                        })
                    }}>
                        <Text
                            style={[
                                authSharedStyles.helperLink,
                                isResending ? authSharedStyles.textLinkDisabled : null,
                            ]}
                        >
                            {isResending ? t("auth.verify.resending") : t("auth.verify.resend")}
                        </Text>
                    </Pressable>
                </View>
            </View>
        </View>
    )
}
