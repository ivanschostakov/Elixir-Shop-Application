import { Pressable, Text, View } from "react-native"
import { router } from "expo-router"

import { ProfileHeroCard } from "@/components/profile/profile-hero-card"
import { ProfileQuickActions } from "@/components/profile/profile-quick-actions"
import { FeedTemplate } from "@/components/templates/feed-template"
import { ROUTES } from "@/constants/routes"
import { useProfileAvatar } from "@/hooks/profile/use-profile-avatar"
import { useAuth } from "@/providers/auth-provider"
import { useLanguage } from "@/providers/language-provider"
import { ProfileScreenStyles } from "@/screens/profile/profile-screen.styles"
import { getProfileInitials } from "@/utils/profile/get-profile-initials"

export default function ProfileScreen() {
    const { signOut, user } = useAuth()
    const { t } = useLanguage()
    const fullName = [user?.name, user?.surname].filter(Boolean).join(" ").trim()
    const displayName = fullName || t("profile.fallbackName")
    const initials = getProfileInitials(displayName)

    const {
        avatarUri,
        isUpdatingAvatar,
        handleChangePhoto,
        handleRemovePhoto,
    } = useProfileAvatar({
        userId: user?.id,
        t,
    })

    const handleSignOut = async () => {
        await signOut()
        router.replace(ROUTES.login)
    }

    return (
        <FeedTemplate
            contentContainerStyle={ProfileScreenStyles.content}
            scrollViewStyle={ProfileScreenStyles.container}
            style={ProfileScreenStyles.screen}
        >
            <ProfileHeroCard
                avatarUri={avatarUri}
                initials={initials}
                displayName={displayName}
                username={user?.username}
                isActive={user?.isActive}
                isVerified={user?.isVerified}
                isUpdatingAvatar={isUpdatingAvatar}
                onChangePhoto={handleChangePhoto}
                onRemovePhoto={handleRemovePhoto}
            />

            <Pressable
                accessibilityLabel={t("profile.history.open")}
                accessibilityRole="button"
                onPress={() => router.push(ROUTES.profileHistory)}
                style={({ pressed }) => [
                    ProfileScreenStyles.historyCardButton,
                    pressed && ProfileScreenStyles.historyCardButtonPressed,
                ]}
            >
                <View style={ProfileScreenStyles.sectionCard}>
                    <View style={ProfileScreenStyles.historyCardHeader}>
                        <View style={ProfileScreenStyles.historyCardCopy}>
                            <Text style={ProfileScreenStyles.historyCardTitle}>{t("profile.history.title")}</Text>
                            <Text style={ProfileScreenStyles.historyCardSubtitle}>{t("profile.history.subtitle")}</Text>
                        </View>

                        <Text style={ProfileScreenStyles.historyCardArrow}>
                            {">"}
                        </Text>
                    </View>
                </View>
            </Pressable>

            <ProfileQuickActions onSignOut={handleSignOut} />
        </FeedTemplate>
    )
}
