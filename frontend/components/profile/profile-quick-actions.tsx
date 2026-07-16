import { ActivityIndicator, Pressable, Text, View } from "react-native"

import type { ProfileQuickActionsProps } from "@/components/profile/profile-quick-actions.types"
import { useLanguage } from "@/providers/language-provider"
import { createProfileScreenStyles } from "@/screens/profile/profile-screen.styles"
import { useThemeStyles } from "@/hooks/use-theme-styles"

export function ProfileQuickActions({ isDeletingAccount = false, onDeleteAccount, onSignOut }: ProfileQuickActionsProps) {
    const ProfileScreenStyles = useThemeStyles(createProfileScreenStyles)
    const { t } = useLanguage()

    return (
        <View style={[ProfileScreenStyles.sectionCard, ProfileScreenStyles.sectionCardBottom]}>
            <Text style={ProfileScreenStyles.sectionTitle}>{t("profile.quickActions")}</Text>
            <Text style={ProfileScreenStyles.sectionDescription}>
                {t("profile.quickActionsSubtitle")}
            </Text>

            <Pressable
                accessibilityLabel={t("nav.signOut")}
                accessibilityRole="button"
                onPress={onSignOut}
                style={({ pressed }) => [
                    ProfileScreenStyles.signOutButton,
                    pressed && ProfileScreenStyles.signOutButtonPressed,
                ]}
            >
                <Text style={ProfileScreenStyles.signOutButtonText}>
                    {t("profile.signOutCta")}
                </Text>
            </Pressable>

            <Pressable
                accessibilityLabel={t("profile.deleteAccountCta")}
                accessibilityRole="button"
                disabled={isDeletingAccount}
                onPress={onDeleteAccount}
                style={({ pressed }) => [
                    ProfileScreenStyles.deleteAccountButton,
                    pressed && !isDeletingAccount && ProfileScreenStyles.deleteAccountButtonPressed,
                    isDeletingAccount && ProfileScreenStyles.deleteAccountButtonDisabled,
                ]}
            >
                {isDeletingAccount ? (
                    <ActivityIndicator color="#ffffff" />
                ) : (
                    <Text style={ProfileScreenStyles.deleteAccountButtonText}>
                        {t("profile.deleteAccountCta")}
                    </Text>
                )}
            </Pressable>
        </View>
    )
}
