import { useCallback, useMemo, useState } from "react"
import { ActivityIndicator, Alert, Image, Pressable, Text, TextInput, View } from "react-native"
import { router, useFocusEffect } from "expo-router"

import { createStickyFooterStyles } from "@/components/footer/sticky-footer.styles"
import { FeedTemplate } from "@/components/templates/feed-template"
import { getProductRoute, ROUTES } from "@/constants/routes"
import { useAsyncData } from "@/hooks/shared/use-async-data"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useAuth } from "@/providers/auth-provider"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import { createProfileScreenStyles } from "@/screens/profile/profile-screen.styles"
import {
    attachMyReferrerCode,
    detachMyReferrerCode,
    getMyPromotions,
    getMyReferralProfile,
    selectMyRewardProgram,
} from "@/services/api/users"
import type { ProfilePromotionResponse, ReferralProfileResponse } from "@/services/api/users.types"
import { formatMoney } from "@/utils/formatting"

function formatProfileMoney(value: string | null | undefined) {
    return formatMoney(Number(value ?? 0), "RUB") ?? "0 ₽"
}

function formatProfilePercent(value: string | null | undefined) {
    const amount = Number(value ?? 0)
    return `${new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 }).format(amount)}%`
}

function formatProfileDate(value: string | null | undefined) {
    if (!value) return "—"
    const date = new Date(value)
    return Number.isNaN(date.getTime()) ? "—" : new Intl.DateTimeFormat("ru-RU").format(date)
}

function getProfilePromotionKey(promotion: ProfilePromotionResponse) {
    return `${promotion.kind}-${promotion.category_id ?? promotion.product_id}`
}

export default function ProfileDiscountsScreen() {
    const stickyFooterStyles = useThemeStyles(createStickyFooterStyles)
    const profileStyles = useThemeStyles(createProfileScreenStyles)
    const { user } = useAuth()
    const { t } = useLanguage()
    const { accentPalette } = useTheme()
    const {
        data: referralProfile,
        loading: referralLoading,
        reload: reloadReferralProfile,
        setData: setReferralProfile,
    } = useAsyncData<ReferralProfileResponse | null>({
        deps: [user?.id ?? null],
        enabled: Boolean(user?.id),
        fetcher: getMyReferralProfile,
        initialData: null,
        resetOnLoad: true,
    })
    const {
        data: promotions,
        loading: promotionsLoading,
        reload: reloadPromotions,
    } = useAsyncData<ProfilePromotionResponse[]>({
        deps: [user?.id ?? null],
        enabled: Boolean(user?.id),
        fetcher: getMyPromotions,
        initialData: [],
        resetOnLoad: true,
    })
    const [profilePromoCode, setProfilePromoCode] = useState("")
    const [isApplyingProfilePromo, setIsApplyingProfilePromo] = useState(false)
    const [isDetachingProfilePromo, setIsDetachingProfilePromo] = useState(false)
    const [selectingProgram, setSelectingProgram] = useState<"bonus" | "partner" | null>(null)
    const normalizedProfilePromoCode = useMemo(() => profilePromoCode.trim(), [profilePromoCode])
    const isPartnerProgram = referralProfile?.reward_program === "partner"
    const isBonusProgram = referralProfile?.reward_program === "bonus"
    const currentPromoCode = referralProfile?.referrer_promo_code ?? referralProfile?.promo_code
    const hasCurrentPromoCode = Boolean(isPartnerProgram && currentPromoCode)
    const hasPartnerEarnings = Boolean(
        referralProfile?.own_promo_code
        || Number(referralProfile?.partner_pending_rubles ?? 0) > 0
        || Number(referralProfile?.partner_approved_rubles ?? 0) > 0,
    )

    useFocusEffect(
        useCallback(() => {
            if (user?.id) {
                void reloadReferralProfile({ showLoading: false })
                void reloadPromotions({ showLoading: false })
            }
        }, [reloadPromotions, reloadReferralProfile, user?.id]),
    )

    const chooseProgram = useCallback((program: "bonus" | "partner") => {
        const programName = program === "bonus"
            ? t("profile.referral.bonusProgramTitle")
            : t("profile.referral.partnerProgramTitle")
        Alert.alert(
            t("profile.referral.confirmProgramTitle"),
            `${programName}. ${t("profile.referral.confirmProgramMessage")}`,
            [
                { text: t("common.cancel"), style: "cancel" },
                {
                    text: t("profile.referral.chooseProgramAction"),
                    onPress: () => {
                        setSelectingProgram(program)
                        void selectMyRewardProgram({ program })
                            .then(setReferralProfile)
                            .catch((error) => Alert.alert(
                                t("profile.referral.programSelectionFailed"),
                                error instanceof Error ? error.message : undefined,
                            ))
                            .finally(() => setSelectingProgram(null))
                    },
                },
            ],
        )
    }, [setReferralProfile, t])

    const handleApplyProfilePromo = useCallback(async () => {
        if (!normalizedProfilePromoCode || isApplyingProfilePromo || !isPartnerProgram) {
            return
        }
        setIsApplyingProfilePromo(true)
        try {
            const nextReferralProfile = await attachMyReferrerCode({
                code: normalizedProfilePromoCode,
                confirmed: true,
            })
            setReferralProfile(nextReferralProfile)
            setProfilePromoCode("")
            Alert.alert(t("profile.referral.attachSuccessTitle"), t("profile.referral.attachSuccessMessage"))
        } catch (error) {
            Alert.alert(
                t("profile.referral.attachFailed"),
                error instanceof Error && error.message ? error.message : t("profile.referral.codeInvalid"),
            )
        } finally {
            setIsApplyingProfilePromo(false)
        }
    }, [isApplyingProfilePromo, isPartnerProgram, normalizedProfilePromoCode, setReferralProfile, t])

    const detachProfilePromo = useCallback(async () => {
        if (isDetachingProfilePromo || !isPartnerProgram) {
            return
        }
        setIsDetachingProfilePromo(true)
        try {
            const nextReferralProfile = await detachMyReferrerCode()
            setReferralProfile(nextReferralProfile)
            setProfilePromoCode("")
            Alert.alert(t("profile.referral.detachSuccessTitle"), t("profile.referral.detachSuccessMessage"))
        } catch (error) {
            Alert.alert(
                t("profile.referral.detachFailed"),
                error instanceof Error && error.message ? error.message : undefined,
            )
        } finally {
            setIsDetachingProfilePromo(false)
        }
    }, [isDetachingProfilePromo, isPartnerProgram, setReferralProfile, t])

    const handleDetachProfilePromo = useCallback(() => {
        Alert.alert(
            t("profile.referral.detachConfirmTitle"),
            t("profile.referral.detachConfirmMessage"),
            [
                { text: t("common.cancel"), style: "cancel" },
                {
                    text: t("profile.referral.detachAction"),
                    style: "destructive",
                    onPress: () => void detachProfilePromo(),
                },
            ],
        )
    }, [detachProfilePromo, t])

    const handleOpenPromotion = useCallback((promotion: ProfilePromotionResponse) => {
        if (promotion.kind === "category" && promotion.category_id) {
            router.push({
                pathname: ROUTES.discover,
                params: { tab: "products", categoryId: String(promotion.category_id) },
            })
            return
        }
        router.push(getProductRoute(promotion.product_id))
    }, [])

    const discountsChromeTemplate = useMemo(() => {
        if (!isPartnerProgram || !normalizedProfilePromoCode || hasCurrentPromoCode) {
            return null
        }
        const footerCtaLabel = isApplyingProfilePromo
            ? t("profile.referral.attachLoading")
            : t("profile.referral.attachAction")
        return {
            footer: "nav+customAction" as const,
            slots: {
                footer: (
                    <Pressable
                        accessibilityLabel={footerCtaLabel}
                        accessibilityRole="button"
                        disabled={isApplyingProfilePromo}
                        onPress={() => void handleApplyProfilePromo()}
                        style={({ pressed }) => [
                            stickyFooterStyles.actionButton,
                            { backgroundColor: accentPalette.primary },
                            isApplyingProfilePromo && stickyFooterStyles.actionButtonDisabled,
                            pressed && !isApplyingProfilePromo && {
                                backgroundColor: accentPalette.primaryPressed,
                            },
                        ]}
                    >
                        <Text style={[stickyFooterStyles.actionButtonText, { color: accentPalette.onPrimary }]}>
                            {footerCtaLabel}
                        </Text>
                    </Pressable>
                ),
            },
        }
    }, [
        accentPalette.onPrimary,
        accentPalette.primary,
        accentPalette.primaryPressed,
        handleApplyProfilePromo,
        hasCurrentPromoCode,
        isApplyingProfilePromo,
        isPartnerProgram,
        normalizedProfilePromoCode,
        stickyFooterStyles,
        t,
    ])

    return (
        <FeedTemplate
            chromeTemplate={discountsChromeTemplate}
            contentContainerStyle={profileStyles.content}
            scrollViewStyle={profileStyles.container}
            style={profileStyles.screen}
        >
            {referralProfile?.program_selection_required ? (
                <View style={profileStyles.sectionCard}>
                    <Text style={profileStyles.sectionTitle}>{t("profile.referral.chooseProgramTitle")}</Text>
                    <Text style={profileStyles.sectionDescription}>{t("profile.referral.chooseProgramHint")}</Text>
                    <View style={profileStyles.detailStack}>
                        <View style={profileStyles.metricCard}>
                            <Text style={profileStyles.metricValue}>{t("profile.referral.bonusProgramTitle")}</Text>
                            <Text style={profileStyles.sectionDescription}>{t("profile.referral.bonusProgramHint")}</Text>
                            <Pressable
                                disabled={selectingProgram !== null}
                                onPress={() => chooseProgram("bonus")}
                                style={({ pressed }) => [
                                    profileStyles.primaryActionButton,
                                    selectingProgram !== null && profileStyles.primaryActionButtonDisabled,
                                    pressed && profileStyles.primaryActionButtonPressed,
                                ]}
                            >
                                <Text style={profileStyles.primaryActionButtonText}>
                                    {selectingProgram === "bonus" ? t("profile.referral.chooseProgramLoading") : t("profile.referral.chooseProgramAction")}
                                </Text>
                            </Pressable>
                        </View>
                        <View style={profileStyles.metricCard}>
                            <Text style={profileStyles.metricValue}>{t("profile.referral.partnerProgramTitle")}</Text>
                            <Text style={profileStyles.sectionDescription}>{t("profile.referral.partnerProgramHint")}</Text>
                            <Pressable
                                disabled={selectingProgram !== null}
                                onPress={() => chooseProgram("partner")}
                                style={({ pressed }) => [
                                    profileStyles.primaryActionButton,
                                    selectingProgram !== null && profileStyles.primaryActionButtonDisabled,
                                    pressed && profileStyles.primaryActionButtonPressed,
                                ]}
                            >
                                <Text style={profileStyles.primaryActionButtonText}>
                                    {selectingProgram === "partner" ? t("profile.referral.chooseProgramLoading") : t("profile.referral.chooseProgramAction")}
                                </Text>
                            </Pressable>
                        </View>
                    </View>
                </View>
            ) : null}

            {!referralProfile && referralLoading ? <ActivityIndicator color={accentPalette.primary} /> : null}

            {isBonusProgram && referralProfile && !referralProfile.program_selection_required ? (
                <View style={profileStyles.sectionCard}>
                    <Text style={profileStyles.sectionTitle}>{t("profile.referral.bonusProgramTitle")}</Text>
                    <Text style={profileStyles.sectionDescription}>{t("profile.referral.bonusProgramHint")}</Text>
                    <View style={profileStyles.metricsGrid}>
                        <View style={[profileStyles.metricCard, profileStyles.metricCardCompact, { flexBasis: "47%", flexGrow: 1 }]}>
                            <Text style={profileStyles.metricLabel}>{t("profile.referral.bonusCashbackPercent")}</Text>
                            <Text style={profileStyles.metricValue}>{formatProfilePercent(referralProfile.bonus_cashback_percent ?? "5")}</Text>
                        </View>
                        <View style={[profileStyles.metricCard, profileStyles.metricCardCompact, { flexBasis: "47%", flexGrow: 1 }]}>
                            <Text style={profileStyles.metricLabel}>{t("profile.referral.availableToSpend")}</Text>
                            <Text style={profileStyles.metricValue}>
                                {referralProfile.bonus_wallet_available
                                    ? formatProfileMoney(referralProfile.bonus_rubles)
                                    : t("profile.referral.bonusUnavailable")}
                            </Text>
                        </View>
                        <View style={[profileStyles.metricCard, profileStyles.metricCardCompact, { flexBasis: "100%", flexGrow: 1 }]}>
                            <Text style={profileStyles.metricLabel}>{t("profile.referral.bonusExpiresAt")}</Text>
                            <Text style={profileStyles.metricValue}>{formatProfileDate(referralProfile.bonus_next_expiration_at)}</Text>
                        </View>
                        {referralProfile.bonus_expiring_points > 0 ? (
                            <View style={[profileStyles.metricCard, profileStyles.metricCardCompact, { flexBasis: "100%", flexGrow: 1 }]}>
                                <Text style={profileStyles.metricLabel}>{t("profile.referral.bonusExpiringSoon")}</Text>
                                <Text style={profileStyles.metricValue}>{formatProfileMoney(referralProfile.bonus_expiring_rubles)}</Text>
                            </View>
                        ) : null}
                    </View>
                </View>
            ) : null}

            {isPartnerProgram && referralProfile && !referralProfile.program_selection_required ? (
                <>
                    <View style={profileStyles.sectionCard}>
                        <Text style={profileStyles.sectionTitle}>{t("profile.referral.partnerProgramTitle")}</Text>
                        <View style={profileStyles.metricsGrid}>
                            <View style={[profileStyles.metricCard, profileStyles.metricCardCompact, { flexBasis: "47%", flexGrow: 1 }]}>
                                <Text style={profileStyles.metricLabel}>{t("profile.referral.currentDiscount")}</Text>
                                <Text style={profileStyles.metricValue}>{formatProfilePercent(referralProfile.current_discount_percent)}</Text>
                            </View>
                            <View style={[profileStyles.metricCard, profileStyles.metricCardCompact, { flexBasis: "47%", flexGrow: 1 }]}>
                                <Text style={profileStyles.metricLabel}>{t("profile.referral.attachedPromo")}</Text>
                                <Text style={[profileStyles.metricValue, profileStyles.metricValueCompact]}>{currentPromoCode ?? "—"}</Text>
                            </View>
                        </View>
                        {hasCurrentPromoCode ? (
                            <View style={profileStyles.detailStack}>
                                <Text style={profileStyles.sectionDescription}>{t("profile.referral.attachedHint")}</Text>
                                <Pressable
                                    disabled={isDetachingProfilePromo}
                                    onPress={handleDetachProfilePromo}
                                    style={({ pressed }) => [
                                        profileStyles.secondaryInlineButton,
                                        pressed && profileStyles.secondaryInlineButtonPressed,
                                    ]}
                                >
                                    <Text style={profileStyles.secondaryInlineButtonText}>
                                        {isDetachingProfilePromo ? t("profile.referral.detachLoading") : t("profile.referral.detachAction")}
                                    </Text>
                                </Pressable>
                            </View>
                        ) : (
                            <>
                                <Text style={profileStyles.sectionTitle}>{t("profile.referral.attachCodeLabel")}</Text>
                                <Text style={profileStyles.sectionDescription}>{t("profile.referral.attachHint")}</Text>
                                <View style={profileStyles.formGroup}>
                                    <TextInput
                                        autoCapitalize="characters"
                                        autoCorrect={false}
                                        onChangeText={setProfilePromoCode}
                                        placeholder={t("profile.referral.attachCodePlaceholder")}
                                        placeholderTextColor="#94A3B8"
                                        style={profileStyles.formInput}
                                        value={profilePromoCode}
                                    />
                                </View>
                                {referralProfile.suggested_promo_code ? (
                                    <Pressable
                                        onPress={() => setProfilePromoCode(referralProfile.suggested_promo_code ?? "")}
                                        style={({ pressed }) => [
                                            profileStyles.secondaryInlineButton,
                                            pressed && profileStyles.secondaryInlineButtonPressed,
                                        ]}
                                    >
                                        <Text style={profileStyles.secondaryInlineButtonText}>
                                            {t("profile.referral.useFirmPromo")}: {referralProfile.suggested_promo_code}
                                        </Text>
                                    </Pressable>
                                ) : null}
                            </>
                        )}
                    </View>
                    <View style={profileStyles.sectionCard}>
                        <Text style={profileStyles.sectionTitle}>{t("profile.referral.totalPurchases")}</Text>
                        <View style={profileStyles.metricsGrid}>
                            <View style={[profileStyles.metricCard, profileStyles.metricCardCompact, { flexBasis: "100%", flexGrow: 1 }]}>
                                <Text style={profileStyles.metricLabel}>{t("profile.referral.totalPurchases")}</Text>
                                <Text style={profileStyles.metricValue}>{formatProfileMoney(referralProfile.total_purchases)}</Text>
                            </View>
                            <View style={[profileStyles.metricCard, profileStyles.metricCardCompact, { flexBasis: "47%", flexGrow: 1 }]}>
                                <Text style={profileStyles.metricLabel}>{t("profile.referral.currentMonthPurchases")}</Text>
                                <Text style={profileStyles.metricValue}>{formatProfileMoney(referralProfile.current_month_purchases)}</Text>
                            </View>
                            <View style={[profileStyles.metricCard, profileStyles.metricCardCompact, { flexBasis: "47%", flexGrow: 1 }]}>
                                <Text style={profileStyles.metricLabel}>{t("profile.referral.previousMonthPurchases")}</Text>
                                <Text style={profileStyles.metricValue}>{formatProfileMoney(referralProfile.previous_month_purchases)}</Text>
                            </View>
                        </View>
                    </View>
                    {hasPartnerEarnings ? (
                        <View style={profileStyles.sectionCard}>
                            <Text style={profileStyles.sectionTitle}>{t("profile.referral.partnerEarningsTitle")}</Text>
                            <View style={profileStyles.metricsGrid}>
                                {referralProfile.own_promo_code ? (
                                    <View style={[profileStyles.metricCard, profileStyles.metricCardCompact, { flexBasis: "100%", flexGrow: 1 }]}>
                                        <Text style={profileStyles.metricLabel}>{t("profile.referral.ownPromo")}</Text>
                                        <Text style={[profileStyles.metricValue, profileStyles.metricValueCompact]}>{referralProfile.own_promo_code}</Text>
                                    </View>
                                ) : null}
                                <View style={[profileStyles.metricCard, profileStyles.metricCardCompact, { flexBasis: "47%", flexGrow: 1 }]}>
                                    <Text style={profileStyles.metricLabel}>{t("profile.referral.partnerPending")}</Text>
                                    <Text style={profileStyles.metricValue}>{formatProfileMoney(referralProfile.partner_pending_rubles)}</Text>
                                </View>
                                <View style={[profileStyles.metricCard, profileStyles.metricCardCompact, { flexBasis: "47%", flexGrow: 1 }]}>
                                    <Text style={profileStyles.metricLabel}>{t("profile.referral.partnerApproved")}</Text>
                                    <Text style={profileStyles.metricValue}>{formatProfileMoney(referralProfile.partner_approved_rubles)}</Text>
                                </View>
                                <View style={[profileStyles.metricCard, profileStyles.metricCardCompact, { flexBasis: "100%", flexGrow: 1 }]}>
                                    <Text style={profileStyles.metricLabel}>{t("profile.referral.availableToSpend")}</Text>
                                    <Text style={profileStyles.metricValue}>
                                        {referralProfile.bonus_wallet_available
                                            ? formatProfileMoney(referralProfile.bonus_rubles)
                                            : t("profile.referral.bonusUnavailable")}
                                    </Text>
                                </View>
                            </View>
                        </View>
                    ) : null}
                </>
            ) : null}

            {promotionsLoading || promotions.length ? (
                <View style={[profileStyles.sectionCard, profileStyles.sectionCardBottom]}>
                    <View style={profileStyles.sectionHeader}>
                        <View style={profileStyles.sectionHeaderCopy}>
                            <Text style={profileStyles.sectionTitle}>{t("profile.discounts.offersTitle")}</Text>
                            <Text style={profileStyles.sectionDescription}>{t("profile.discounts.subtitle")}</Text>
                        </View>
                        {promotionsLoading ? <ActivityIndicator color={accentPalette.primary} /> : null}
                    </View>
                    {promotions.length ? (
                        <View style={profileStyles.discountStack}>
                            {promotions.map((promotion) => (
                                <Pressable
                                    accessibilityRole="button"
                                    key={getProfilePromotionKey(promotion)}
                                    onPress={() => handleOpenPromotion(promotion)}
                                    style={({ pressed }) => [profileStyles.discountRow, pressed && profileStyles.discountRowPressed]}
                                >
                                    <Image resizeMode="cover" source={{ uri: promotion.image_url }} style={profileStyles.discountImage} />
                                    <View style={profileStyles.discountCopy}>
                                        <Text style={profileStyles.discountTitle}>{promotion.title}</Text>
                                        <Text numberOfLines={2} style={profileStyles.discountCode}>
                                            {promotion.kind === "category" ? t("profile.discounts.category") : t("profile.discounts.product")}
                                        </Text>
                                    </View>
                                    <View style={profileStyles.discountBadge}>
                                        <Text style={profileStyles.discountValue}>−{formatProfilePercent(promotion.discount_percent)}</Text>
                                    </View>
                                    <Text style={profileStyles.discountArrow}>{">"}</Text>
                                </Pressable>
                            ))}
                        </View>
                    ) : null}
                </View>
            ) : null}
        </FeedTemplate>
    )
}
