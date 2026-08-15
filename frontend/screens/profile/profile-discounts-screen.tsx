import { useCallback, useMemo, useState } from "react"
import { ActivityIndicator, Alert, Image, Pressable, Text, TextInput, View } from "react-native"
import { router, useFocusEffect } from "expo-router"
import { LinearGradient } from "expo-linear-gradient"

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
    const normalizedProfilePromoCode = useMemo(() => profilePromoCode.trim(), [profilePromoCode])
    const currentPromoCode = referralProfile?.referrer_promo_code ?? referralProfile?.promo_code
    const hasCurrentPromoCode = Boolean(currentPromoCode)
    const isPartnerProgram = hasCurrentPromoCode
    const isBonusProgram = Boolean(referralProfile) && !hasCurrentPromoCode
    const hasPartnerEarnings = Boolean(
        referralProfile?.own_promo_code
        || Number(referralProfile?.partner_pending_rubles ?? 0) > 0
        || Number(referralProfile?.partner_approved_rubles ?? 0) > 0,
    )
    const totalPurchases = Number(referralProfile?.total_purchases ?? 0)
    const choiceProgress = Math.max(0, Math.min(1, totalPurchases / 30000))
    const partnerProgress = Math.max(0, Math.min(1, totalPurchases / 100000))

    useFocusEffect(
        useCallback(() => {
            if (user?.id) {
                void reloadReferralProfile({ showLoading: false })
                void reloadPromotions({ showLoading: false })
            }
        }, [reloadPromotions, reloadReferralProfile, user?.id]),
    )

    const applyProfilePromo = useCallback(async () => {
        if (!normalizedProfilePromoCode || isApplyingProfilePromo) {
            return
        }
        setIsApplyingProfilePromo(true)
        try {
            const nextReferralProfile = await attachMyReferrerCode({
                code: normalizedProfilePromoCode,
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
    }, [isApplyingProfilePromo, normalizedProfilePromoCode, setReferralProfile, t])

    const handleApplyProfilePromo = useCallback(() => {
        if (!normalizedProfilePromoCode || isApplyingProfilePromo || hasCurrentPromoCode) {
            return
        }
        void applyProfilePromo()
    }, [
        applyProfilePromo,
        hasCurrentPromoCode,
        isApplyingProfilePromo,
        normalizedProfilePromoCode,
    ])

    const detachProfilePromo = useCallback(async () => {
        if (isDetachingProfilePromo) {
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
    }, [isDetachingProfilePromo, setReferralProfile, t])

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
        if (
            hasCurrentPromoCode
            ||
            !normalizedProfilePromoCode
        ) {
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
            {referralProfile ? (
                <LinearGradient
                    colors={[accentPalette.primary, accentPalette.primaryPressed]}
                    end={{ x: 1, y: 1 }}
                    start={{ x: 0, y: 0 }}
                    style={profileStyles.benefitsHero}
                >
                    <View style={profileStyles.benefitsHeroGlow} />
                    <Text style={profileStyles.benefitsHeroEyebrow}>{t("profile.discounts.heroEyebrow")}</Text>
                    <Text style={profileStyles.benefitsHeroTitle}>{t("profile.discounts.heroTitle")}</Text>
                    <Text style={profileStyles.benefitsHeroDescription}>{t("profile.discounts.heroDescription")}</Text>
                    <View style={profileStyles.benefitsHeroMetrics}>
                        <View style={profileStyles.benefitsHeroMetric}>
                            <Text style={profileStyles.benefitsHeroMetricLabel}>{t("profile.referral.currentDiscount")}</Text>
                            <Text style={profileStyles.benefitsHeroMetricValue}>
                                {formatProfilePercent(referralProfile.current_discount_percent)}
                            </Text>
                        </View>
                        <View style={profileStyles.benefitsHeroMetric}>
                            <Text style={profileStyles.benefitsHeroMetricLabel}>{t("profile.referral.bonusRubles")}</Text>
                            <Text style={profileStyles.benefitsHeroMetricValue}>
                                {referralProfile.bonus_wallet_available
                                    ? formatProfileMoney(referralProfile.bonus_rubles)
                                    : "—"}
                            </Text>
                        </View>
                    </View>
                    <View style={profileStyles.benefitsStatusPill}>
                        <Text style={profileStyles.benefitsStatusPillText}>
                            {t(hasCurrentPromoCode
                                ? "profile.discounts.statusPartner"
                                : "profile.discounts.statusCashback")}
                        </Text>
                    </View>
                </LinearGradient>
            ) : null}

            {!referralProfile && referralLoading ? <ActivityIndicator color={accentPalette.primary} /> : null}

            {referralProfile ? (
                <View style={profileStyles.sectionCard}>
                    <View style={profileStyles.benefitsSectionHeading}>
                        <View style={profileStyles.benefitsNumberBadge}>
                            <Text style={profileStyles.benefitsNumberBadgeText}>01</Text>
                        </View>
                        <View style={profileStyles.sectionHeaderCopy}>
                            <Text style={profileStyles.sectionTitle}>{t("profile.discounts.promoTitle")}</Text>
                            <Text style={profileStyles.sectionDescription}>{t("profile.discounts.promoDescription")}</Text>
                        </View>
                    </View>
                    {hasCurrentPromoCode ? (
                        <View style={profileStyles.benefitsActivePromo}>
                            <View style={profileStyles.benefitsActivePromoCopy}>
                                <Text style={profileStyles.benefitsChoiceKicker}>{t("profile.discounts.promoActive")}</Text>
                                <Text style={profileStyles.benefitsPromoCode}>{currentPromoCode}</Text>
                            </View>
                            <View style={profileStyles.benefitsDiscountPill}>
                                <Text style={profileStyles.benefitsDiscountPillText}>
                                    −{formatProfilePercent(referralProfile.current_discount_percent)}
                                </Text>
                            </View>
                        </View>
                    ) : (
                        <View style={profileStyles.benefitsInfoStrip}>
                            <Text style={profileStyles.benefitsInfoStripText}>{t("profile.discounts.promoEmptyHint")}</Text>
                        </View>
                    )}
                    {!hasCurrentPromoCode ? (
                        <View style={profileStyles.formGroup}>
                            <Text style={profileStyles.formLabel}>{t("profile.referral.attachCodeLabel")}</Text>
                            <TextInput
                                autoCapitalize="characters"
                                autoCorrect={false}
                                onChangeText={setProfilePromoCode}
                                placeholder={t("profile.referral.attachCodePlaceholder")}
                                placeholderTextColor="#94A3B8"
                                style={profileStyles.formInput}
                                value={profilePromoCode}
                            />
                            <Text style={profileStyles.formHint}>{t("profile.discounts.promoInputHint")}</Text>
                        </View>
                    ) : null}
                    {!hasCurrentPromoCode && referralProfile.suggested_promo_code ? (
                        <Pressable
                            onPress={() => setProfilePromoCode(referralProfile.suggested_promo_code ?? "")}
                            style={({ pressed }) => [
                                profileStyles.benefitsSoftAction,
                                pressed && profileStyles.secondaryInlineButtonPressed,
                            ]}
                        >
                            <Text style={profileStyles.benefitsSoftActionText}>
                                {t("profile.referral.useFirmPromo")}: {referralProfile.suggested_promo_code}
                            </Text>
                        </Pressable>
                    ) : null}
                    {hasCurrentPromoCode ? (
                        <Pressable
                            disabled={isDetachingProfilePromo}
                            onPress={handleDetachProfilePromo}
                            style={({ pressed }) => [
                                profileStyles.secondaryInlineButton,
                                pressed && profileStyles.secondaryInlineButtonPressed,
                            ]}
                        >
                            <Text style={profileStyles.secondaryInlineButtonText}>
                                {isDetachingProfilePromo
                                    ? t("profile.referral.detachLoading")
                                    : t("profile.referral.detachAction")}
                            </Text>
                        </Pressable>
                    ) : null}
                </View>
            ) : null}

            {referralProfile ? (
                <View style={profileStyles.sectionCard}>
                    <Text style={profileStyles.sectionTitle}>{t("profile.discounts.howItWorksTitle")}</Text>
                    <Text style={profileStyles.sectionDescription}>{t("profile.discounts.howItWorksSubtitle")}</Text>
                    <View style={profileStyles.benefitsGuideStack}>
                        <View style={profileStyles.benefitsGuideCard}>
                            <View style={profileStyles.benefitsGuideHeader}>
                                <View style={profileStyles.benefitsGuideIndex}><Text style={profileStyles.benefitsGuideIndexText}>1</Text></View>
                                <View style={profileStyles.sectionHeaderCopy}>
                                    <Text style={profileStyles.subsectionTitle}>{t("profile.discounts.guideCashbackTitle")}</Text>
                                    <Text style={profileStyles.sectionDescription}>{t("profile.discounts.guideCashbackText")}</Text>
                                </View>
                            </View>
                            <Text style={profileStyles.benefitsRuleText}>{t("profile.discounts.guideCashbackRules")}</Text>
                        </View>
                        <View style={profileStyles.benefitsGuideCard}>
                            <View style={profileStyles.benefitsGuideHeader}>
                                <View style={profileStyles.benefitsGuideIndex}><Text style={profileStyles.benefitsGuideIndexText}>2</Text></View>
                                <View style={profileStyles.sectionHeaderCopy}>
                                    <Text style={profileStyles.subsectionTitle}>{t("profile.discounts.guidePromoTitle")}</Text>
                                    <Text style={profileStyles.sectionDescription}>{t("profile.discounts.guidePromoText")}</Text>
                                </View>
                            </View>
                            <View style={profileStyles.benefitsScaleRow}>
                                {[["0–30K", "3%"], ["40K", "4%"], ["100K", "10%"], ["200K", "20%"]].map(([amount, percent]) => (
                                    <View key={amount} style={profileStyles.benefitsScaleItem}>
                                        <Text style={profileStyles.benefitsScalePercent}>{percent}</Text>
                                        <Text style={profileStyles.benefitsScaleAmount}>{amount}</Text>
                                    </View>
                                ))}
                            </View>
                        </View>
                        <View style={profileStyles.benefitsGuideCard}>
                            <View style={profileStyles.benefitsGuideHeader}>
                                <View style={profileStyles.benefitsGuideIndex}><Text style={profileStyles.benefitsGuideIndexText}>3</Text></View>
                                <View style={profileStyles.sectionHeaderCopy}>
                                    <Text style={profileStyles.subsectionTitle}>{t("profile.discounts.guidePartnerTitle")}</Text>
                                    <Text style={profileStyles.sectionDescription}>{t("profile.discounts.guidePartnerText")}</Text>
                                </View>
                            </View>
                            <Text style={profileStyles.benefitsRuleText}>{t("profile.discounts.guidePartnerRules")}</Text>
                        </View>
                    </View>
                </View>
            ) : null}

            {referralProfile ? (
                <View style={profileStyles.sectionCard}>
                    <View style={profileStyles.benefitsProgressHeader}>
                        <View>
                            <Text style={profileStyles.metricLabel}>{t("profile.discounts.progressTitle")}</Text>
                            <Text style={profileStyles.metricValue}>{formatProfileMoney(referralProfile.total_purchases)}</Text>
                        </View>
                        <Text style={profileStyles.benefitsProgressTarget}>
                            {formatProfileMoney(hasCurrentPromoCode ? "100000" : "30000")}
                        </Text>
                    </View>
                    <View style={profileStyles.benefitsProgressTrack}>
                        <View
                            style={[
                                profileStyles.benefitsProgressFill,
                                { width: `${Math.round((hasCurrentPromoCode ? partnerProgress : choiceProgress) * 100)}%` },
                            ]}
                        />
                    </View>
                    <Text style={profileStyles.sectionDescription}>
                        {t(hasCurrentPromoCode
                            ? "profile.discounts.progressOwnPromoHint"
                            : "profile.discounts.progressChoiceHint")}
                    </Text>
                </View>
            ) : null}

            {isBonusProgram && referralProfile ? (
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

            {isPartnerProgram && referralProfile ? (
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
                        <Text style={profileStyles.sectionDescription}>{t("profile.discounts.partnerGrowthActive")}</Text>
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
