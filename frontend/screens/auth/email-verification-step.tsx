import { useEffect, useRef, useState } from "react"
import { ActivityIndicator, Pressable, Text, TextInput, View } from "react-native"
import { Path, Svg } from "react-native-svg"

import { BACK_ARROW_PATH } from "@/components/header/app-header.constants"
import { useLanguage } from "@/providers/language-provider"
import { authSharedStyles } from "@/screens/auth/auth-shared.styles"
import type { EmailVerificationStepProps } from "@/screens/auth/email-verification-step.types"
import { colors } from "@/theme/colors"

export default function EmailVerificationStep({
    email,
    isChecking,
    isResending,
    onEditEmail,
    onResend,
    onVerify,
    statusMessage,
}: EmailVerificationStepProps) {
    const { t } = useLanguage()
    const [verificationCode, setVerificationCode] = useState("")
    const verificationInputRef = useRef<TextInput>(null)

    useEffect(() => {
        const focusTimeout = setTimeout(() => {
            verificationInputRef.current?.focus()
        }, 150)

        return () => clearTimeout(focusTimeout)
    }, [email])

    const handleCodeChange = (value: string) => {
        const nextCode = value.replace(/\D/g, "").slice(0, 6)
        setVerificationCode(nextCode)

        if (nextCode.length === 6 && !isChecking) {
            void handleVerify(nextCode)
        }
    }

    const handleVerify = async (code: string) => {
        const verified = await onVerify(code)

        if (!verified) {
            setVerificationCode("")
            requestAnimationFrame(() => verificationInputRef.current?.focus())
        }
    }

    const codeDigits = Array.from({ length: 6 }, (_, index) => verificationCode[index] ?? "")

    return (
        <View style={authSharedStyles.verificationStep}>
            <Pressable
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
                    <Path d={BACK_ARROW_PATH} fill={colors.text} />
                </Svg>
            </Pressable>

            <View style={authSharedStyles.verificationPanel}>
                <Text style={authSharedStyles.verificationText}>
                    {t("auth.verify.description")}{" "}
                    <Text style={authSharedStyles.verificationEmail}>{email}</Text>.
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
                        style={authSharedStyles.codeCells}
                    >
                        {codeDigits.map((digit, index) => (
                            <View
                                key={index}
                                style={[
                                    authSharedStyles.codeCell,
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
                        <ActivityIndicator color={colors.primary} />
                        <Text style={authSharedStyles.verificationCheckingText}>{t("auth.verify.checking")}</Text>
                    </View>
                ) : null}

                <View style={authSharedStyles.helperRow}>
                    <Text style={authSharedStyles.helperText}>{t("auth.verify.resendHint")}</Text>
                    <Pressable disabled={isResending} onPress={() => void onResend()}>
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
