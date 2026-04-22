import { Pressable, Text, View } from "react-native"

import type { ProfileQuickActionsProps } from "@/components/profile/profile-quick-actions.types"
import { useLanguage } from "@/providers/language-provider"
import { ProfileScreenStyles } from "@/screens/profile/profile-screen.styles"

export function ProfileQuickActions({ onSignOut }: ProfileQuickActionsProps) {
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
        </View>
    )
}
