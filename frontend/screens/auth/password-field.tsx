import { useState } from "react"
import { Pressable, Text, TextInput, View } from "react-native"

import { useLanguage } from "@/providers/language-provider"
import { createAuthSharedStyles } from "@/screens/auth/auth-shared.styles"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import type { PasswordFieldProps } from "@/screens/auth/password-field.types"

export default function PasswordField({
    label,
    onChangeText,
    onFocus,
    placeholder,
    returnKeyType,
    value,
}: PasswordFieldProps) {
    const authSharedStyles = useThemeStyles(createAuthSharedStyles)
    const [isVisible, setIsVisible] = useState(false)
    const { t } = useLanguage()

    return (
        <>
            <Text style={authSharedStyles.fieldLabel}>{label}</Text>
            <View style={authSharedStyles.inputRow}>
                <TextInput
                    autoCapitalize="none"
                    autoCorrect={false}
                    onChangeText={onChangeText}
                    onFocus={onFocus}
                    placeholder={placeholder}
                    returnKeyType={returnKeyType}
                    secureTextEntry={!isVisible}
                    style={authSharedStyles.inputField}
                    value={value}
                />
                <Pressable
                    onPress={() => setIsVisible((current) => !current)}
                    style={({ pressed }) => [
                        authSharedStyles.visibilityButton,
                        pressed && authSharedStyles.visibilityButtonPressed,
                    ]}
                >
                    <Text style={authSharedStyles.visibilityButtonText}>
                        {isVisible ? t("common.hide") : t("common.show")}
                    </Text>
                </Pressable>
            </View>
        </>
    )
}
