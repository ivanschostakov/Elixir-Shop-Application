import { Pressable, Text, View } from "react-native"
import { router } from "expo-router"

import { ProfileHeroCard } from "@/components/profile/profile-hero-card"
import { ProfileQuickActions } from "@/components/profile/profile-quick-actions"
import { FeedTemplate } from "@/components/templates/feed-template"
import { ROUTES } from "@/constants/routes"
import { useProfileAvatar } from "@/hooks/profile/use-profile-avatar"
import { useAsyncData } from "@/hooks/shared/use-async-data"
import { useAuth } from "@/providers/auth-provider"
import { useLanguage } from "@/providers/language-provider"
import { ProfileScreenStyles } from "@/screens/profile/profile-screen.styles"
import { getMyReferralProfile } from "@/services/api/users"
import type { ReferralProfileResponse } from "@/services/api/users.types"
import { formatMoney } from "@/utils/formatting"
import { getProfileInitials } from "@/utils/profile/get-profile-initials"

function formatProfileMoney(value: string | null | undefined) {
    return formatMoney(Number(value ?? 0), "RUB") ?? "0 ₽"
}

function formatProfilePercent(value: string | null | undefined) {
    const amount = Number(value ?? 0)
    return `${new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 }).format(amount)}%`
}

export default function ProfileScreen() {
    const { signOut, user } = useAuth()
    const { t } = useLanguage()
    const fullName = [user?.name, user?.surname].filter(Boolean).join(" ").trim()
    const displayName = fullName || t("profile.fallbackName")
    const initials = getProfileInitials(displayName)
    const { data: referralProfile } = useAsyncData<ReferralProfileResponse | null>({
        deps: [user?.id ?? null],
        enabled: Boolean(user?.id),
        fetcher: getMyReferralProfile,
        initialData: null,
        resetOnLoad: true,
    })

    const {
        avatarUri,
        isUpdatingAvatar,
        handleChangePhoto,
        handleRemovePhoto,
    } = useProfileAvatar({
        userId: user?.id,
        t,
    })
    const shouldShowReferralDetails = Boolean(referralProfile?.referrer_promo_code)

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

            {shouldShowReferralDetails && referralProfile ? (
                <View style={ProfileScreenStyles.sectionCard}>
                    <View style={ProfileScreenStyles.sectionHeader}>
                        <View style={ProfileScreenStyles.sectionHeaderCopy}>
                            <Text style={ProfileScreenStyles.sectionTitle}>{t("profile.referral.title")}</Text>
                            <Text style={ProfileScreenStyles.sectionDescription}>{t("profile.referral.subtitle")}</Text>
                        </View>
                    </View>

                    <View style={ProfileScreenStyles.metricsGrid}>
                        <View style={[ProfileScreenStyles.metricCard, { flexBasis: "47%", flexGrow: 1 }]}>
                            <Text style={ProfileScreenStyles.metricLabel}>{t("profile.referral.totalPurchases")}</Text>
                            <Text style={ProfileScreenStyles.metricValue}>
                                {formatProfileMoney(referralProfile.total_purchases)}
                            </Text>
                        </View>
                        <View style={[ProfileScreenStyles.metricCard, { flexBasis: "47%", flexGrow: 1 }]}>
                            <Text style={ProfileScreenStyles.metricLabel}>{t("profile.referral.currentDiscount")}</Text>
                            <Text style={ProfileScreenStyles.metricValue}>
                                {formatProfilePercent(referralProfile.current_discount_percent)}
                            </Text>
                        </View>
                        <View style={[ProfileScreenStyles.metricCard, { flexBasis: "47%", flexGrow: 1 }]}>
                            <Text style={ProfileScreenStyles.metricLabel}>{t("profile.referral.deposit")}</Text>
                            <Text style={ProfileScreenStyles.metricValue}>
                                {formatProfileMoney(referralProfile.deposit_balance)}
                            </Text>
                        </View>
                        <View style={[ProfileScreenStyles.metricCard, { flexBasis: "47%", flexGrow: 1 }]}>
                            <Text style={ProfileScreenStyles.metricLabel}>{t("profile.referral.commissions")}</Text>
                            <Text style={ProfileScreenStyles.metricValue}>
                                {formatProfileMoney(referralProfile.accrued_commissions)}
                            </Text>
                        </View>
                    </View>

                    <View style={ProfileScreenStyles.detailStack}>
                        <View style={ProfileScreenStyles.detailRow}>
                            <Text style={ProfileScreenStyles.detailLabel}>{t("profile.referral.currentMonth")}</Text>
                            <Text style={ProfileScreenStyles.detailValue}>
                                {formatProfileMoney(referralProfile.current_month_purchases)}
                            </Text>
                        </View>
                        <View style={ProfileScreenStyles.detailDivider} />
                        <View style={ProfileScreenStyles.detailRow}>
                            <Text style={ProfileScreenStyles.detailLabel}>{t("profile.referral.previousMonth")}</Text>
                            <Text style={ProfileScreenStyles.detailValue}>
                                {formatProfileMoney(referralProfile.previous_month_purchases)}
                            </Text>
                        </View>
                        <View style={ProfileScreenStyles.detailDivider} />
                        <View style={ProfileScreenStyles.detailRow}>
                            <Text style={ProfileScreenStyles.detailLabel}>{t("profile.referral.referrerPromo")}</Text>
                            <Text style={ProfileScreenStyles.detailValue}>
                                {referralProfile.referrer_promo_code}
                            </Text>
                        </View>
                        {referralProfile.own_promo_code ? (
                            <>
                                <View style={ProfileScreenStyles.detailDivider} />
                                <View style={ProfileScreenStyles.detailRow}>
                                    <Text style={ProfileScreenStyles.detailLabel}>{t("profile.referral.ownPromo")}</Text>
                                    <Text style={ProfileScreenStyles.detailValue}>
                                        {referralProfile.own_promo_code}
                                    </Text>
                                </View>
                            </>
                        ) : null}
                    </View>
                </View>
            ) : null}

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

            <Pressable
                accessibilityLabel={t("profile.drafts.open")}
                accessibilityRole="button"
                onPress={() => router.push(ROUTES.profileDrafts)}
                style={({ pressed }) => [
                    ProfileScreenStyles.historyCardButton,
                    pressed && ProfileScreenStyles.historyCardButtonPressed,
                ]}
            >
                <View style={ProfileScreenStyles.sectionCard}>
                    <View style={ProfileScreenStyles.historyCardHeader}>
                        <View style={ProfileScreenStyles.historyCardCopy}>
                            <Text style={ProfileScreenStyles.historyCardTitle}>{t("profile.drafts.title")}</Text>
                            <Text style={ProfileScreenStyles.historyCardSubtitle}>{t("profile.drafts.subtitle")}</Text>
                        </View>

                        <Text style={ProfileScreenStyles.historyCardArrow}>
                            {">"}
                        </Text>
                    </View>
                </View>
            </Pressable>

            <View style={ProfileScreenStyles.sectionCard}>
                <Text style={ProfileScreenStyles.sectionDescription}>
                    {t("profile.legalSubtitle")}
                </Text>

                <Pressable
                    accessibilityLabel={t("profile.openContacts")}
                    accessibilityRole="button"
                    onPress={() => router.push(ROUTES.contacts)}
                    style={({ pressed }) => [
                        ProfileScreenStyles.historyCardButton,
                        pressed && ProfileScreenStyles.historyCardButtonPressed,
                    ]}
                >
                    <View style={ProfileScreenStyles.sectionCard}>
                        <View style={ProfileScreenStyles.historyCardHeader}>
                            <Text style={ProfileScreenStyles.historyCardTitle}>{t("nav.contacts")}</Text>
                            <Text style={ProfileScreenStyles.historyCardArrow}>{">"}</Text>
                        </View>
                    </View>
                </Pressable>

                <Pressable
                    accessibilityLabel={t("profile.openRequisites")}
                    accessibilityRole="button"
                    onPress={() => router.push(ROUTES.requisites)}
                    style={({ pressed }) => [
                        ProfileScreenStyles.historyCardButton,
                        pressed && ProfileScreenStyles.historyCardButtonPressed,
                    ]}
                >
                    <View style={ProfileScreenStyles.sectionCard}>
                        <View style={ProfileScreenStyles.historyCardHeader}>
                            <Text style={ProfileScreenStyles.historyCardTitle}>{t("nav.requisites")}</Text>
                            <Text style={ProfileScreenStyles.historyCardArrow}>{">"}</Text>
                        </View>
                    </View>
                </Pressable>

                <Pressable
                    accessibilityLabel={t("profile.openPublicOffer")}
                    accessibilityRole="button"
                    onPress={() => router.push(ROUTES.publicOffer)}
                    style={({ pressed }) => [
                        ProfileScreenStyles.historyCardButton,
                        pressed && ProfileScreenStyles.historyCardButtonPressed,
                    ]}
                >
                    <View style={ProfileScreenStyles.sectionCard}>
                        <View style={ProfileScreenStyles.historyCardHeader}>
                            <Text style={ProfileScreenStyles.historyCardTitle}>{t("nav.publicOffer")}</Text>
                            <Text style={ProfileScreenStyles.historyCardArrow}>{">"}</Text>
                        </View>
                    </View>
                </Pressable>
            </View>

            <ProfileQuickActions onSignOut={handleSignOut} />
        </FeedTemplate>
    )
}
