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
    const hasCurrentPromoCode = Boolean(referralProfile?.promo_code)

    useFocusEffect(
        useCallback(() => {
            if (user?.id) {
                void reloadReferralProfile({ showLoading: false })
                void reloadPromotions({ showLoading: false })
            }
        }, [reloadPromotions, reloadReferralProfile, user?.id]),
    )

    const handleApplyProfilePromo = useCallback(async () => {
        if (!normalizedProfilePromoCode) {
            Alert.alert(t("profile.referral.codeRequired"))
            return
        }
        if (isApplyingProfilePromo) {
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
        } catch (applyError) {
            Alert.alert(
                t("profile.referral.attachFailed"),
                applyError instanceof Error && applyError.message
                    ? applyError.message
                    : t("profile.referral.codeInvalid"),
            )
        } finally {
            setIsApplyingProfilePromo(false)
        }
    }, [isApplyingProfilePromo, normalizedProfilePromoCode, setReferralProfile, t])

    const handleDetachProfilePromo = useCallback(async () => {
        if (isDetachingProfilePromo) {
            return
        }

        setIsDetachingProfilePromo(true)
        try {
            const nextReferralProfile = await detachMyReferrerCode()
            setReferralProfile(nextReferralProfile)
            setProfilePromoCode("")
            Alert.alert(t("profile.referral.detachSuccessTitle"), t("profile.referral.detachSuccessMessage"))
        } catch (detachError) {
            Alert.alert(
                t("profile.referral.detachFailed"),
                detachError instanceof Error && detachError.message ? detachError.message : undefined,
            )
        } finally {
            setIsDetachingProfilePromo(false)
        }
    }, [isDetachingProfilePromo, setReferralProfile, t])

    const handleOpenPromotion = useCallback((promotion: ProfilePromotionResponse) => {
        if (promotion.kind === "category" && promotion.category_id) {
            router.push({
                pathname: ROUTES.discover,
                params: {
                    tab: "products",
                    categoryId: String(promotion.category_id),
                },
            })
            return
        }

        router.push(getProductRoute(promotion.product_id))
    }, [])

    const discountsChromeTemplate = useMemo(() => {
        if (!normalizedProfilePromoCode || hasCurrentPromoCode) {
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
                        onPress={() => {
                            void handleApplyProfilePromo()
                        }}
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
            <View style={profileStyles.sectionCard}>
                <View style={profileStyles.sectionHeader}>
                    <View style={profileStyles.sectionHeaderCopy}>
                        <Text style={profileStyles.sectionTitle}>{t("profile.referral.title")}</Text>
                        <Text style={profileStyles.sectionDescription}>
                            {t("profile.discounts.pageSubtitle")}
                        </Text>
                    </View>
                    {referralLoading ? <ActivityIndicator color={accentPalette.primary} /> : null}
                </View>

                <View style={profileStyles.metricsGrid}>
                    <View style={[profileStyles.metricCard, { flexBasis: "100%", flexGrow: 1 }]}>
                        <Text style={profileStyles.metricLabel}>{t("profile.referral.referrerPromo")}</Text>
                        <Text style={[profileStyles.metricValue, profileStyles.metricValueCompact]}>
                            {referralProfile?.promo_code ?? "—"}
                        </Text>
                    </View>
                    <View style={[profileStyles.metricCard, { flexBasis: "47%", flexGrow: 1 }]}>
                        <Text style={profileStyles.metricLabel}>{t("profile.referral.currentDiscount")}</Text>
                        <Text style={profileStyles.metricValue}>
                            {formatProfilePercent(referralProfile?.current_discount_percent)}
                        </Text>
                    </View>
                    <View style={[profileStyles.metricCard, { flexBasis: "47%", flexGrow: 1 }]}>
                        <Text style={profileStyles.metricLabel}>{t("profile.referral.bonusRubles")}</Text>
                        <Text style={profileStyles.metricValue}>
                            {formatProfileMoney(referralProfile?.bonus_rubles)}
                        </Text>
                    </View>
                </View>
            </View>

            <View style={profileStyles.sectionCard}>
                <Text style={profileStyles.sectionTitle}>{t("profile.referral.attachCodeLabel")}</Text>
                {hasCurrentPromoCode && referralProfile?.promo_code ? (
                    <View style={profileStyles.detailStack}>
                        <Text style={profileStyles.sectionDescription}>
                            {t("profile.referral.attachedHint")}
                        </Text>
                        <Pressable
                            accessibilityLabel={t("profile.referral.detachAction")}
                            accessibilityRole="button"
                            disabled={isDetachingProfilePromo}
                            onPress={() => {
                                void handleDetachProfilePromo()
                            }}
                            style={({ pressed }) => [
                                profileStyles.secondaryInlineButton,
                                pressed && !isDetachingProfilePromo && profileStyles.secondaryInlineButtonPressed,
                                isDetachingProfilePromo && profileStyles.primaryActionButtonDisabled,
                            ]}
                        >
                            <Text style={profileStyles.secondaryInlineButtonText}>
                                {isDetachingProfilePromo
                                    ? t("profile.referral.detachLoading")
                                    : t("profile.referral.detachAction")}
                            </Text>
                        </Pressable>
                    </View>
                ) : (
                    <>
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
                    </>
                )}
            </View>

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
                                accessibilityLabel={`${promotion.title}, ${formatProfilePercent(promotion.discount_percent)}`}
                                accessibilityRole="button"
                                key={getProfilePromotionKey(promotion)}
                                onPress={() => handleOpenPromotion(promotion)}
                                style={({ pressed }) => [
                                    profileStyles.discountRow,
                                    pressed && profileStyles.discountRowPressed,
                                ]}
                            >
                                <Image
                                    resizeMode="cover"
                                    source={{ uri: promotion.image_url }}
                                    style={profileStyles.discountImage}
                                />
                                <View style={profileStyles.discountCopy}>
                                    <Text style={profileStyles.discountTitle}>{promotion.title}</Text>
                                    <Text numberOfLines={2} style={profileStyles.discountCode}>
                                        {promotion.kind === "category"
                                            ? t("profile.discounts.category")
                                            : t("profile.discounts.product")}
                                    </Text>
                                </View>
                                <View style={profileStyles.discountBadge}>
                                    <Text style={profileStyles.discountValue}>
                                        −{formatProfilePercent(promotion.discount_percent)}
                                    </Text>
                                </View>
                                <Text style={profileStyles.discountArrow}>{">"}</Text>
                            </Pressable>
                        ))}
                    </View>
                ) : promotionsLoading ? null : (
                    <Text style={profileStyles.sectionDescription}>{t("profile.discounts.empty")}</Text>
                )}
            </View>
        </FeedTemplate>
    )
}
