import { Pressable, Text, View } from "react-native"

import type { ProfileAccountDetailsProps } from "@/components/profile/profile-account-details.types"
import { useCopyableProfileValue } from "@/hooks/profile/use-copyable-profile-value"
import { useLanguage } from "@/providers/language-provider"
import { ProfileScreenStyles } from "@/screens/profile/profile-screen.styles"

export function ProfileAccountDetails({
    email,
    username,
}: ProfileAccountDetailsProps) {
    const { t } = useLanguage()
    const { handleCopy } = useCopyableProfileValue({ t })
    const usernameValue = username ? `@${username}` : null

    return (
        <View style={ProfileScreenStyles.sectionCard}>
            <Text style={ProfileScreenStyles.sectionTitle}>{t("profile.accountDetails")}</Text>

            <Pressable
                accessibilityLabel={t("profile.email")}
                accessibilityRole={email ? "button" : undefined}
                disabled={!email}
                onPress={() => void handleCopy(email)}
                style={({ pressed }) => [
                    ProfileScreenStyles.detailRowButton,
                    pressed && email && ProfileScreenStyles.detailRowButtonPressed,
                ]}
            >
                <View style={ProfileScreenStyles.detailRow}>
                    <Text style={ProfileScreenStyles.detailLabel}>{t("profile.email")}</Text>
                    <Text style={ProfileScreenStyles.detailValue}>
                        {email ?? t("profile.notProvided")}
                    </Text>
                </View>
            </Pressable>

            <View style={ProfileScreenStyles.detailDivider} />

            <Pressable
                accessibilityLabel={t("profile.username")}
                accessibilityRole={usernameValue ? "button" : undefined}
                disabled={!usernameValue}
                onPress={() => void handleCopy(usernameValue)}
                style={({ pressed }) => [
                    ProfileScreenStyles.detailRowButton,
                    pressed && usernameValue && ProfileScreenStyles.detailRowButtonPressed,
                ]}
            >
                <View style={ProfileScreenStyles.detailRow}>
                    <Text style={ProfileScreenStyles.detailLabel}>{t("profile.username")}</Text>
                    <Text style={ProfileScreenStyles.detailValue}>
                        {usernameValue ?? t("profile.notProvided")}
                    </Text>
                </View>
            </Pressable>
        </View>
    )
}
