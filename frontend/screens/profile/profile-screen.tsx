import { router } from "expo-router"

import { ProfileAccountDetails } from "@/components/profile/profile-account-details"
import { ProfileHeroCard } from "@/components/profile/profile-hero-card"
import { ProfileQuickActions } from "@/components/profile/profile-quick-actions"
import { ProfileWebsiteIdentityCard } from "@/components/profile/profile-website-identity-card"
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

            <ProfileAccountDetails
                email={user?.email}
                username={user?.username}
            />

            <ProfileWebsiteIdentityCard />

            <ProfileQuickActions onSignOut={handleSignOut} />
        </FeedTemplate>
    )
}
