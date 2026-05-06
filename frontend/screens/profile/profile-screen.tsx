import { useState } from "react"
import { ActivityIndicator, Alert, Pressable, Text, TextInput, View } from "react-native"
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
import { attachMyReferrerCode, checkMyReferrerCode, getMyReferralProfile } from "@/services/api/users"
import type { ReferralProfileResponse } from "@/services/api/users.types"
import { formatMoney } from "@/utils/formatting"
import { getProfileInitials } from "@/utils/profile/get-profile-initials"
import { getErrorMessage, showBackendErrorAlert } from "@/utils/errors"

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
    const [referrerCodeInput, setReferrerCodeInput] = useState("")
    const [referrerCodeError, setReferrerCodeError] = useState<string | null>(null)
    const [isSubmittingReferrerCode, setIsSubmittingReferrerCode] = useState(false)
    const fullName = [user?.name, user?.surname].filter(Boolean).join(" ").trim()
    const displayName = fullName || t("profile.fallbackName")
    const initials = getProfileInitials(displayName)
    const {
        data: referralProfile,
        error: referralProfileError,
        loading: referralProfileLoading,
        reload: reloadReferralProfile,
    } = useAsyncData<ReferralProfileResponse | null>({
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

    const handleSignOut = async () => {
        await signOut()
        router.replace(ROUTES.login)
    }

    const applyReferrerCode = async (code: string, confirmed = false) => {
        const nextProfile = await attachMyReferrerCode({ code, confirmed })
        await reloadReferralProfile({ showLoading: false })
        setReferrerCodeInput("")
        setReferrerCodeError(null)
        return nextProfile
    }

    const handleSubmitReferrerCode = async () => {
        const code = referrerCodeInput.trim()
        if (!code || isSubmittingReferrerCode) {
            setReferrerCodeError(t("profile.referral.codeRequired"))
            return
        }

        setIsSubmittingReferrerCode(true)
        setReferrerCodeError(null)

        try {
            const check = await checkMyReferrerCode({ code })
            if (!check.is_valid) {
                setReferrerCodeError(check.reason ?? t("profile.referral.codeInvalid"))
                return
            }

            const normalizedCode = check.code ?? code
            if (check.requires_confirmation) {
                Alert.alert(
                    t("profile.referral.changeWarningTitle"),
                    check.warning ?? t("profile.referral.changeWarningMessage"),
                    [
                        { text: t("common.cancel"), style: "cancel" },
                        {
                            text: t("common.apply"),
                            style: "destructive",
                            onPress: () => {
                                void applyReferrerCode(normalizedCode, true).catch((applyError) => {
                                    const message = getErrorMessage(applyError, t("profile.referral.attachFailed"))
                                    setReferrerCodeError(message)
                                    showBackendErrorAlert(applyError, message)
                                })
                            },
                        },
                    ],
                )
                return
            }

            await applyReferrerCode(normalizedCode)
        } catch (submitError) {
            const message = getErrorMessage(submitError, t("profile.referral.attachFailed"))
            setReferrerCodeError(message)
            showBackendErrorAlert(submitError, message)
        } finally {
            setIsSubmittingReferrerCode(false)
        }
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

            <View style={ProfileScreenStyles.sectionCard}>
                <View style={ProfileScreenStyles.sectionHeader}>
                    <View style={ProfileScreenStyles.sectionHeaderCopy}>
                        <Text style={ProfileScreenStyles.sectionTitle}>{t("profile.referral.title")}</Text>
                        <Text style={ProfileScreenStyles.sectionDescription}>{t("profile.referral.subtitle")}</Text>
                    </View>
                </View>

                {referralProfileLoading ? (
                    <View style={ProfileScreenStyles.loadingBox}>
                        <ActivityIndicator />
                    </View>
                ) : referralProfileError ? (
                    <View style={ProfileScreenStyles.errorBox}>
                        <Text style={ProfileScreenStyles.errorText}>{referralProfileError}</Text>
                    </View>
                ) : referralProfile ? (
                    <>
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
                                    {referralProfile.referrer_promo_code ?? t("profile.notProvided")}
                                </Text>
                            </View>
                            <View style={ProfileScreenStyles.detailDivider} />
                            <View style={ProfileScreenStyles.detailRow}>
                                <Text style={ProfileScreenStyles.detailLabel}>{t("profile.referral.ownPromo")}</Text>
                                <Text style={ProfileScreenStyles.detailValue}>
                                    {referralProfile.own_promo_code ?? t("profile.referral.ownPromoPending")}
                                </Text>
                            </View>
                        </View>

                        <View style={ProfileScreenStyles.formGroup}>
                            <Text style={ProfileScreenStyles.formLabel}>{t("profile.referral.attachCodeLabel")}</Text>
                            <TextInput
                                autoCapitalize="characters"
                                autoCorrect={false}
                                editable={!isSubmittingReferrerCode}
                                onChangeText={(value) => {
                                    setReferrerCodeInput(value)
                                    if (referrerCodeError) {
                                        setReferrerCodeError(null)
                                    }
                                }}
                                placeholder={t("profile.referral.attachCodePlaceholder")}
                                placeholderTextColor="#94A3B8"
                                style={ProfileScreenStyles.formInput}
                                value={referrerCodeInput}
                            />
                            {referrerCodeError ? (
                                <Text style={ProfileScreenStyles.errorText}>{referrerCodeError}</Text>
                            ) : (
                                <Text style={ProfileScreenStyles.formHint}>{t("profile.referral.attachHint")}</Text>
                            )}
                            <Pressable
                                accessibilityLabel={t("profile.referral.attachAction")}
                                accessibilityRole="button"
                                disabled={isSubmittingReferrerCode}
                                onPress={() => {
                                    void handleSubmitReferrerCode()
                                }}
                                style={({ pressed }) => [
                                    ProfileScreenStyles.primaryActionButton,
                                    pressed && !isSubmittingReferrerCode && ProfileScreenStyles.primaryActionButtonPressed,
                                    isSubmittingReferrerCode && ProfileScreenStyles.avatarViewerActionDisabled,
                                ]}
                            >
                                <Text style={ProfileScreenStyles.primaryActionButtonText}>
                                    {isSubmittingReferrerCode
                                        ? t("profile.referral.attachLoading")
                                        : t("profile.referral.attachAction")}
                                </Text>
                            </Pressable>
                        </View>
                    </>
                ) : null}
            </View>

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
