import { useCallback, useMemo, useState } from "react"
import { ActivityIndicator, Alert, Image, Pressable, Text, TextInput, View } from "react-native"
import { router, useFocusEffect } from "expo-router"
import { LinearGradient } from "expo-linear-gradient"

import { FeedTemplate } from "@/components/templates/feed-template"
import { getProductRoute, ROUTES } from "@/constants/routes"
import { useAsyncData } from "@/hooks/shared/use-async-data"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useAuth } from "@/providers/auth-provider"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import { createProfileDiscountsScreenStyles } from "@/screens/profile/profile-discounts-screen.styles"
import {
    attachMyReferrerCode,
    detachMyReferrerCode,
    getMyPromotions,
    getMyReferralProfile,
} from "@/services/api/users"
import type { ProfilePromotionResponse, ReferralProfileResponse } from "@/services/api/users.types"
import { formatMoney } from "@/utils/formatting"

function formatProfileMoney(value: string | number | null | undefined) {
    return formatMoney(Number(value ?? 0), "RUB") ?? "0 ₽"
}

function formatProfilePercent(value: string | number | null | undefined) {
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

const REFERRAL_DISCOUNT_GOALS = [
    { target: 30000, percent: 3 },
    { target: 40000, percent: 4 },
    { target: 50000, percent: 5 },
    { target: 60000, percent: 6 },
    { target: 70000, percent: 7 },
    { target: 80000, percent: 8 },
    { target: 90000, percent: 9 },
    { target: 100000, percent: 10 },
    { target: 110000, percent: 11 },
    { target: 120000, percent: 12 },
    { target: 130000, percent: 13 },
    { target: 140000, percent: 14 },
    { target: 150000, percent: 15 },
    { target: 160000, percent: 16 },
    { target: 170000, percent: 17 },
    { target: 180000, percent: 18 },
    { target: 190000, percent: 19 },
    { target: 200000, percent: 20 },
] as const

export default function ProfileDiscountsScreen() {
    const styles = useThemeStyles(createProfileDiscountsScreenStyles)
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
    const [isScaleExpanded, setIsScaleExpanded] = useState(false)
    const [areRulesExpanded, setAreRulesExpanded] = useState(false)

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
    const currentDiscountPercent = hasCurrentPromoCode
        ? Math.max(3, Number(referralProfile?.current_discount_percent ?? 0))
        : Number(referralProfile?.bonus_cashback_percent ?? 5)
    const nextDiscountGoal = hasCurrentPromoCode
        ? REFERRAL_DISCOUNT_GOALS.find(({ percent }) => percent > currentDiscountPercent) ?? null
        : null
    const progressStart = hasCurrentPromoCode
        ? currentDiscountPercent <= 3 ? 0 : currentDiscountPercent * 10000
        : 0
    const progressTarget = hasCurrentPromoCode
        ? nextDiscountGoal?.target ?? 200000
        : 100000
    const progressRange = Math.max(1, progressTarget - progressStart)
    const progressValue = Math.max(0, Math.min(1, (totalPurchases - progressStart) / progressRange))

    useFocusEffect(
        useCallback(() => {
            if (user?.id) {
                void reloadReferralProfile({ showLoading: false })
                void reloadPromotions({ showLoading: false })
            }
        }, [reloadPromotions, reloadReferralProfile, user?.id]),
    )

    const applyProfilePromo = useCallback(async () => {
        if (!normalizedProfilePromoCode || isApplyingProfilePromo) return
        setIsApplyingProfilePromo(true)
        try {
            const nextReferralProfile = await attachMyReferrerCode({ code: normalizedProfilePromoCode })
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
        if (!normalizedProfilePromoCode || isApplyingProfilePromo || hasCurrentPromoCode) return
        void applyProfilePromo()
    }, [applyProfilePromo, hasCurrentPromoCode, isApplyingProfilePromo, normalizedProfilePromoCode])

    const detachProfilePromo = useCallback(async () => {
        if (isDetachingProfilePromo) return
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

    return (
        <FeedTemplate contentContainerStyle={styles.content} scrollViewStyle={styles.container} style={styles.screen}>
            {!referralProfile && referralLoading ? (
                <ActivityIndicator color={accentPalette.primary} style={styles.loading} />
            ) : null}

            {referralProfile ? (
                <LinearGradient
                    colors={[accentPalette.primary, accentPalette.primaryPressed]}
                    end={{ x: 1, y: 1 }}
                    start={{ x: 0, y: 0 }}
                    style={styles.summaryCard}
                >
                    <View style={styles.summaryGlow} />
                    <View>
                        <Text style={styles.summaryEyebrow}>{t("profile.discounts.activeNow")}</Text>
                        <View style={styles.summaryValueRow}>
                            <Text style={styles.summaryValue}>{formatProfilePercent(currentDiscountPercent)}</Text>
                            <Text style={styles.summaryValueLabel}>
                                {t(hasCurrentPromoCode
                                    ? "profile.discounts.discountOnPurchase"
                                    : "profile.discounts.bonusAfterPayment")}
                            </Text>
                        </View>
                    </View>
                    <View style={styles.summaryMeta}>
                        <Text style={styles.summaryMetaLabel}>
                            {t(hasCurrentPromoCode
                                ? "profile.discounts.promoCodeShort"
                                : "profile.referral.availableToSpend")}
                        </Text>
                        <Text numberOfLines={1} style={styles.summaryMetaValue}>
                            {hasCurrentPromoCode
                                ? currentPromoCode
                                : referralProfile.bonus_wallet_available
                                    ? formatProfileMoney(referralProfile.bonus_rubles)
                                    : t("profile.referral.bonusUnavailable")}
                        </Text>
                    </View>
                </LinearGradient>
            ) : null}

            {referralProfile ? (
                <View style={styles.card}>
                    <View style={styles.cardHeader}>
                        <View style={styles.cardHeaderCopy}>
                            <Text style={styles.cardTitle}>{t("profile.discounts.promoTitle")}</Text>
                            <Text style={styles.cardDescription}>
                                {t(hasCurrentPromoCode
                                    ? "profile.discounts.promoAttachedHint"
                                    : "profile.discounts.promoEmptyHint")}
                            </Text>
                        </View>
                        {hasCurrentPromoCode ? (
                            <View style={[styles.activeBadge, { backgroundColor: accentPalette.primaryMuted }]}>
                                <Text style={[styles.activeBadgeText, { color: accentPalette.primary }]}>
                                    {t("profile.discounts.available")}
                                </Text>
                            </View>
                        ) : null}
                    </View>

                    {hasCurrentPromoCode ? (
                        <View style={styles.promoSurface}>
                            <View style={styles.promoCopy}>
                                <Text style={styles.smallLabel}>{t("profile.discounts.promoActive")}</Text>
                                <Text numberOfLines={1} style={styles.promoCode}>{currentPromoCode}</Text>
                            </View>
                            <Pressable
                                accessibilityRole="button"
                                disabled={isDetachingProfilePromo}
                                onPress={handleDetachProfilePromo}
                                style={({ pressed }) => [styles.unlinkButton, pressed && styles.unlinkButtonPressed]}
                            >
                                <Text style={styles.unlinkButtonText}>
                                    {isDetachingProfilePromo
                                        ? t("profile.referral.detachLoading")
                                        : t("profile.referral.detachAction")}
                                </Text>
                            </Pressable>
                        </View>
                    ) : (
                        <View style={styles.promoForm}>
                            <View style={styles.promoInputRow}>
                                <TextInput
                                    autoCapitalize="characters"
                                    autoCorrect={false}
                                    onChangeText={setProfilePromoCode}
                                    onSubmitEditing={handleApplyProfilePromo}
                                    placeholder={t("profile.referral.attachCodePlaceholder")}
                                    placeholderTextColor="#94A3B8"
                                    returnKeyType="done"
                                    style={styles.promoInput}
                                    value={profilePromoCode}
                                />
                                <Pressable
                                    accessibilityRole="button"
                                    disabled={!normalizedProfilePromoCode || isApplyingProfilePromo}
                                    onPress={handleApplyProfilePromo}
                                    style={({ pressed }) => [
                                        styles.primaryButton,
                                        { backgroundColor: pressed ? accentPalette.primaryPressed : accentPalette.primary },
                                        (!normalizedProfilePromoCode || isApplyingProfilePromo) && styles.primaryButtonDisabled,
                                    ]}
                                >
                                    {isApplyingProfilePromo ? (
                                        <ActivityIndicator color={accentPalette.onPrimary} />
                                    ) : (
                                        <Text style={[styles.primaryButtonText, { color: accentPalette.onPrimary }]}>
                                            {t("profile.referral.attachAction")}
                                        </Text>
                                    )}
                                </Pressable>
                            </View>
                            <Text style={styles.cardDescription}>{t("profile.discounts.promoInputHint")}</Text>
                            {referralProfile.suggested_promo_code ? (
                                <Pressable
                                    onPress={() => setProfilePromoCode(referralProfile.suggested_promo_code ?? "")}
                                    style={({ pressed }) => [styles.suggestionButton, pressed && styles.suggestionButtonPressed]}
                                >
                                    <Text style={styles.suggestionButtonText}>
                                        {t("profile.referral.useFirmPromo")}: {referralProfile.suggested_promo_code}
                                    </Text>
                                </Pressable>
                            ) : null}
                        </View>
                    )}
                </View>
            ) : null}

            {referralProfile ? (
                <View style={styles.card}>
                    <View style={styles.cardHeaderCopy}>
                        <Text style={styles.cardTitle}>
                            {t(hasCurrentPromoCode
                                ? "profile.discounts.discountProgressTitle"
                                : "profile.discounts.ownPromoGoalTitle")}
                        </Text>
                        <Text style={styles.cardDescription}>
                            {t(hasCurrentPromoCode
                                ? "profile.discounts.progressOwnPromoHint"
                                : "profile.discounts.progressChoiceHint")}
                        </Text>
                    </View>
                    <View style={styles.progressNumbers}>
                        <View>
                            <Text style={styles.smallLabel}>{t("profile.discounts.progressTitle")}</Text>
                            <Text style={styles.progressValue}>{formatProfileMoney(totalPurchases)}</Text>
                        </View>
                        <View style={styles.progressTarget}>
                            <Text style={styles.smallLabel}>
                                {t(nextDiscountGoal
                                    ? "profile.discounts.nextLevel"
                                    : hasCurrentPromoCode
                                        ? "profile.discounts.maximumLevel"
                                        : "profile.referral.ownPromo")}
                            </Text>
                            <Text style={styles.progressTargetValue}>
                                {nextDiscountGoal
                                    ? `${nextDiscountGoal.percent}% · ${formatProfileMoney(nextDiscountGoal.target)}`
                                    : hasCurrentPromoCode
                                        ? "20%"
                                        : formatProfileMoney(100000)}
                            </Text>
                        </View>
                    </View>
                    <View style={styles.progressTrack}>
                        <View
                            style={[
                                styles.progressFill,
                                { backgroundColor: accentPalette.primary, width: `${Math.round(progressValue * 100)}%` },
                            ]}
                        />
                    </View>
                    {hasCurrentPromoCode && nextDiscountGoal ? (
                        <Text style={styles.progressHint}>
                            {t("profile.referral.discountRemaining")}: {formatProfileMoney(Math.max(0, nextDiscountGoal.target - totalPurchases))}
                        </Text>
                    ) : null}
                    {hasCurrentPromoCode && isScaleExpanded ? (
                        <View style={styles.ladder}>
                            {REFERRAL_DISCOUNT_GOALS.map(({ target, percent }) => (
                                <View key={target} style={styles.ladderItem}>
                                    <Text style={styles.ladderAmount}>
                                        {target === 30000
                                            ? `0–${formatProfileMoney(target)}`
                                            : formatProfileMoney(target)}
                                    </Text>
                                    <Text
                                        style={[
                                            styles.ladderPercent,
                                            percent === currentDiscountPercent && { color: accentPalette.primary },
                                        ]}
                                    >
                                        {percent}%
                                    </Text>
                                </View>
                            ))}
                        </View>
                    ) : null}
                    {hasCurrentPromoCode ? (
                        <Pressable
                            accessibilityRole="button"
                            onPress={() => setIsScaleExpanded((value) => !value)}
                            style={({ pressed }) => [styles.disclosureButton, pressed && styles.disclosureButtonPressed]}
                        >
                            <Text style={styles.disclosureText}>
                                {t(isScaleExpanded
                                    ? "profile.discounts.hideScale"
                                    : "profile.discounts.showScale")}
                            </Text>
                            <Text style={styles.disclosureSymbol}>{isScaleExpanded ? "−" : "+"}</Text>
                        </Pressable>
                    ) : null}
                </View>
            ) : null}

            {referralProfile ? (
                <View style={styles.card}>
                    <View style={styles.cardHeaderCopy}>
                        <Text style={styles.cardTitle}>{t("profile.discounts.howItWorksTitle")}</Text>
                        <Text style={styles.cardDescription}>{t("profile.discounts.howItWorksSubtitle")}</Text>
                    </View>
                    {areRulesExpanded ? (
                        <View style={styles.ruleList}>
                            <View style={styles.ruleRow}>
                                <View style={[styles.ruleDot, { backgroundColor: accentPalette.primary }]} />
                                <View style={styles.ruleCopy}>
                                    <Text style={styles.ruleTitle}>{t("profile.discounts.guideCashbackTitle")}</Text>
                                    <Text style={styles.ruleText}>{t("profile.discounts.guideCashbackText")}</Text>
                                    <Text style={styles.ruleText}>{t("profile.discounts.guideCashbackRules")}</Text>
                                </View>
                            </View>
                            <View style={styles.ruleRow}>
                                <View style={[styles.ruleDot, { backgroundColor: accentPalette.primary }]} />
                                <View style={styles.ruleCopy}>
                                    <Text style={styles.ruleTitle}>{t("profile.discounts.guidePromoTitle")}</Text>
                                    <Text style={styles.ruleText}>{t("profile.discounts.guidePromoText")}</Text>
                                </View>
                            </View>
                            <View style={[styles.ruleRow, styles.ruleRowLast]}>
                                <View style={[styles.ruleDot, { backgroundColor: accentPalette.primary }]} />
                                <View style={styles.ruleCopy}>
                                    <Text style={styles.ruleTitle}>{t("profile.discounts.guidePartnerTitle")}</Text>
                                    <Text style={styles.ruleText}>{t("profile.discounts.guidePartnerText")}</Text>
                                    <Text style={styles.ruleText}>{t("profile.discounts.guidePartnerRules")}</Text>
                                </View>
                            </View>
                        </View>
                    ) : null}
                    <Pressable
                        accessibilityRole="button"
                        onPress={() => setAreRulesExpanded((value) => !value)}
                        style={({ pressed }) => [styles.disclosureButton, pressed && styles.disclosureButtonPressed]}
                    >
                        <Text style={styles.disclosureText}>
                            {t(areRulesExpanded
                                ? "profile.discounts.hideRules"
                                : "profile.discounts.showRules")}
                        </Text>
                        <Text style={styles.disclosureSymbol}>{areRulesExpanded ? "−" : "+"}</Text>
                    </Pressable>
                </View>
            ) : null}

            {isBonusProgram && referralProfile ? (
                <View style={styles.card}>
                    <Text style={styles.cardTitle}>{t("profile.discounts.bonusDetailsTitle")}</Text>
                    <View style={styles.statList}>
                        <View style={styles.statRow}>
                            <Text style={styles.statLabel}>{t("profile.referral.availableToSpend")}</Text>
                            <Text style={styles.statValue}>
                                {referralProfile.bonus_wallet_available
                                    ? formatProfileMoney(referralProfile.bonus_rubles)
                                    : t("profile.referral.bonusUnavailable")}
                            </Text>
                        </View>
                        <View style={styles.statRow}>
                            <Text style={styles.statLabel}>{t("profile.referral.bonusExpiresAt")}</Text>
                            <Text style={styles.statValue}>{formatProfileDate(referralProfile.bonus_next_expiration_at)}</Text>
                        </View>
                        <View style={[styles.statRow, styles.statRowLast]}>
                            <Text style={styles.statLabel}>{t("profile.referral.bonusExpiringSoon")}</Text>
                            <Text style={styles.statValue}>{formatProfileMoney(referralProfile.bonus_expiring_rubles)}</Text>
                        </View>
                    </View>
                </View>
            ) : null}

            {isPartnerProgram && referralProfile ? (
                <View style={styles.card}>
                    <Text style={styles.cardTitle}>{t("profile.discounts.purchaseDetailsTitle")}</Text>
                    <View style={styles.statList}>
                        <View style={styles.statRow}>
                            <Text style={styles.statLabel}>{t("profile.referral.currentMonthPurchases")}</Text>
                            <Text style={styles.statValue}>{formatProfileMoney(referralProfile.current_month_purchases)}</Text>
                        </View>
                        <View style={[styles.statRow, styles.statRowLast]}>
                            <Text style={styles.statLabel}>{t("profile.referral.previousMonthPurchases")}</Text>
                            <Text style={styles.statValue}>{formatProfileMoney(referralProfile.previous_month_purchases)}</Text>
                        </View>
                    </View>
                </View>
            ) : null}

            {isPartnerProgram && hasPartnerEarnings && referralProfile ? (
                <View style={styles.card}>
                    <Text style={styles.cardTitle}>{t("profile.referral.partnerEarningsTitle")}</Text>
                    <View style={styles.statList}>
                        {referralProfile.own_promo_code ? (
                            <View style={styles.statRow}>
                                <Text style={styles.statLabel}>{t("profile.referral.ownPromo")}</Text>
                                <Text style={styles.statValue}>{referralProfile.own_promo_code}</Text>
                            </View>
                        ) : null}
                        <View style={styles.statRow}>
                            <Text style={styles.statLabel}>{t("profile.referral.partnerPending")}</Text>
                            <Text style={styles.statValue}>{formatProfileMoney(referralProfile.partner_pending_rubles)}</Text>
                        </View>
                        <View style={styles.statRow}>
                            <Text style={styles.statLabel}>{t("profile.referral.partnerApproved")}</Text>
                            <Text style={styles.statValue}>{formatProfileMoney(referralProfile.partner_approved_rubles)}</Text>
                        </View>
                        <View style={[styles.statRow, styles.statRowLast]}>
                            <Text style={styles.statLabel}>{t("profile.referral.availableToSpend")}</Text>
                            <Text style={styles.statValue}>
                                {referralProfile.bonus_wallet_available
                                    ? formatProfileMoney(referralProfile.bonus_rubles)
                                    : t("profile.referral.bonusUnavailable")}
                            </Text>
                        </View>
                    </View>
                </View>
            ) : null}

            {promotionsLoading || promotions.length ? (
                <View style={styles.card}>
                    <View style={styles.cardHeader}>
                        <View style={styles.cardHeaderCopy}>
                            <Text style={styles.cardTitle}>{t("profile.discounts.offersTitle")}</Text>
                            <Text style={styles.cardDescription}>{t("profile.discounts.subtitle")}</Text>
                        </View>
                        {promotionsLoading ? <ActivityIndicator color={accentPalette.primary} /> : null}
                    </View>
                    {promotions.length ? (
                        <View style={styles.promotionStack}>
                            {promotions.map((promotion) => (
                                <Pressable
                                    accessibilityRole="button"
                                    key={getProfilePromotionKey(promotion)}
                                    onPress={() => handleOpenPromotion(promotion)}
                                    style={({ pressed }) => [styles.promotionRow, pressed && styles.promotionRowPressed]}
                                >
                                    <Image resizeMode="cover" source={{ uri: promotion.image_url }} style={styles.promotionImage} />
                                    <View style={styles.promotionCopy}>
                                        <Text numberOfLines={2} style={styles.promotionTitle}>{promotion.title}</Text>
                                        <Text numberOfLines={1} style={styles.promotionSubtitle}>
                                            {promotion.kind === "category"
                                                ? t("profile.discounts.category")
                                                : t("profile.discounts.product")}
                                        </Text>
                                    </View>
                                    <Text style={styles.promotionDiscount}>−{formatProfilePercent(promotion.discount_percent)}</Text>
                                    <Text style={styles.promotionArrow}>›</Text>
                                </Pressable>
                            ))}
                        </View>
                    ) : null}
                </View>
            ) : null}
        </FeedTemplate>
    )
}
