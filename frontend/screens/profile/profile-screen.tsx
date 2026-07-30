import { useCallback, useMemo, useState } from "react"
import { Alert, Image, Pressable, Text, TextInput, View } from "react-native"
import { router, useFocusEffect } from "expo-router"

import { ProfileHeroCard } from "@/components/profile/profile-hero-card"
import { ProfileQuickActions } from "@/components/profile/profile-quick-actions"
import { FeedTemplate } from "@/components/templates/feed-template"
import { createStickyFooterStyles } from "@/components/footer/sticky-footer.styles"
import { getProductRoute, ROUTES } from "@/constants/routes"
import { useProfileAvatar } from "@/hooks/profile/use-profile-avatar"
import { useAsyncData } from "@/hooks/shared/use-async-data"
import { useAuth } from "@/providers/auth-provider"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import { createProfileScreenStyles } from "@/screens/profile/profile-screen.styles"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { attachMyReferrerCode, detachMyReferrerCode, getMyPromotions, getMyReferralProfile } from "@/services/api/users"
import type { ProfilePromotionResponse, ReferralProfileResponse } from "@/services/api/users.types"
import { formatMoney } from "@/utils/formatting"
import { getProfileInitials } from "@/utils/profile/get-profile-initials"
import { themeAccentPalettes, type ThemeAccentName } from "@/theme/colors"

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

export default function ProfileScreen() {
    const stickyFooterStyles = useThemeStyles(createStickyFooterStyles)
    const ProfileScreenStyles = useThemeStyles(createProfileScreenStyles)
    const { deleteAccount, signOut, user } = useAuth()
    const { language, setLanguage, t } = useLanguage()
    const { accentName, accentPalette, setAccentName, themeName, toggleTheme } = useTheme()
    const fullName = [user?.name, user?.surname].filter(Boolean).join(" ").trim()
    const displayName = fullName || t("profile.fallbackName")
    const initials = getProfileInitials(displayName)
    const {
        data: referralProfile,
        reload: reloadReferralProfile,
        setData: setReferralProfile,
    } = useAsyncData<ReferralProfileResponse | null>({
        deps: [user?.id ?? null],
        enabled: Boolean(user?.id),
        fetcher: getMyReferralProfile,
        initialData: null,
        resetOnLoad: true,
    })
    const [profilePromoCode, setProfilePromoCode] = useState("")
    const [isApplyingProfilePromo, setIsApplyingProfilePromo] = useState(false)
    const [isDetachingProfilePromo, setIsDetachingProfilePromo] = useState(false)
    const [isDeletingAccount, setIsDeletingAccount] = useState(false)
    const normalizedProfilePromoCode = useMemo(() => profilePromoCode.trim(), [profilePromoCode])
    const {
        data: promotions,
        reload: reloadPromotions,
    } = useAsyncData<ProfilePromotionResponse[]>({
        deps: [user?.id ?? null],
        enabled: Boolean(user?.id),
        fetcher: getMyPromotions,
        initialData: [],
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
    const shouldShowReferralDetails = Boolean(referralProfile?.promo_code)
    const accentOptions: ThemeAccentName[] = [
        "vividBlue",
        "archivedBlue",
        "teal",
        "emerald",
        "rose",
        "amber",
        "blackWhite",
    ]
    const accentLabel = language === "ru"
        ? "Акцент"
        : language === "kz"
          ? "Негізгі түс"
          : "Accent"

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
                detachError instanceof Error && detachError.message
                    ? detachError.message
                    : undefined,
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

    const handleSignOut = async () => {
        await signOut()
        router.replace(ROUTES.login)
    }

    const handleDeleteAccount = useCallback(() => {
        if (isDeletingAccount) {
            return
        }

        Alert.alert(
            t("profile.deleteAccountConfirmTitle"),
            t("profile.deleteAccountConfirmMessage"),
            [
                {
                    text: t("common.cancel"),
                    style: "cancel",
                },
                {
                    text: t("profile.deleteAccountConfirmAction"),
                    style: "destructive",
                    onPress: () => {
                        setIsDeletingAccount(true)
                        void deleteAccount()
                            .then(() => {
                                router.replace(ROUTES.login)
                            })
                            .catch((deleteError) => {
                                Alert.alert(
                                    t("profile.deleteAccountFailedTitle"),
                                    deleteError instanceof Error && deleteError.message
                                        ? deleteError.message
                                        : t("profile.deleteAccountFailedMessage"),
                                )
                            })
                            .finally(() => {
                                setIsDeletingAccount(false)
                            })
                    },
                },
            ],
        )
    }, [deleteAccount, isDeletingAccount, t])

    const profileChromeTemplate = useMemo(() => {
        if (!normalizedProfilePromoCode || shouldShowReferralDetails) {
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
                            pressed && !isApplyingProfilePromo && { backgroundColor: accentPalette.primaryPressed },
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
        stickyFooterStyles,
        isApplyingProfilePromo,
        normalizedProfilePromoCode,
        shouldShowReferralDetails,
        t,
    ])

    return (
        <FeedTemplate
            chromeTemplate={profileChromeTemplate}
            contentContainerStyle={ProfileScreenStyles.content}
            scrollViewStyle={ProfileScreenStyles.container}
            style={ProfileScreenStyles.screen}
        >
            <ProfileHeroCard
                avatarUri={avatarUri}
                contactValue={user?.phoneNumber ?? user?.email}
                initials={initials}
                displayName={displayName}
                isActive={user?.isActive}
                isVerified={user?.isVerified}
                isUpdatingAvatar={isUpdatingAvatar}
                onChangePhoto={handleChangePhoto}
                onRemovePhoto={handleRemovePhoto}
            />

            <Pressable
                accessibilityLabel={t("profile.personalData.open")}
                accessibilityRole="button"
                onPress={() => router.push(ROUTES.personalData)}
                style={({ pressed }) => [
                    ProfileScreenStyles.historyCardButton,
                    pressed && ProfileScreenStyles.historyCardButtonPressed,
                ]}
            >
                <View style={ProfileScreenStyles.sectionCard}>
                    <View style={ProfileScreenStyles.historyCardHeader}>
                        <View style={ProfileScreenStyles.historyCardCopy}>
                            <Text style={ProfileScreenStyles.historyCardTitle}>{t("profile.personalData.title")}</Text>
                            <Text style={ProfileScreenStyles.historyCardSubtitle}>{t("profile.personalData.subtitle")}</Text>
                        </View>

                        <Text style={ProfileScreenStyles.historyCardArrow}>
                            {">"}
                        </Text>
                    </View>
                </View>
            </Pressable>

            <View style={ProfileScreenStyles.sectionCard}>
                <Text style={ProfileScreenStyles.sectionTitle}>{t("profile.language")}</Text>
                <Text style={ProfileScreenStyles.sectionDescription}>{t("profile.languageSubtitle")}</Text>
                <View style={ProfileScreenStyles.preferencesChipRow}>
                    {[
                        { code: "ru" as const, label: "🇷🇺 RU" },
                        { code: "en" as const, label: "🇬🇧 EN" },
                        { code: "kz" as const, label: "🇰🇿 KZ" },
                    ].map((languageOption) => (
                        <Pressable
                            key={languageOption.code}
                            accessibilityRole="button"
                            accessibilityLabel={languageOption.label}
                            onPress={() => setLanguage(languageOption.code)}
                            style={({ pressed }) => [
                                ProfileScreenStyles.preferenceChip,
                                language === languageOption.code && [
                                    ProfileScreenStyles.preferenceChipActive,
                                    {
                                        borderColor: accentPalette.primary,
                                        backgroundColor: accentPalette.primaryMuted,
                                    },
                                ],
                                pressed && ProfileScreenStyles.preferenceChipPressed,
                            ]}
                        >
                            <Text
                                style={[
                                    ProfileScreenStyles.preferenceChipText,
                                    language === languageOption.code && [
                                        ProfileScreenStyles.preferenceChipTextActive,
                                        { color: accentPalette.primary },
                                    ],
                                ]}
                            >
                                {languageOption.label}
                            </Text>
                        </Pressable>
                    ))}
                </View>
                <View style={ProfileScreenStyles.themeModeRow}>
                    <Pressable
                        accessibilityRole="button"
                        accessibilityLabel={themeName === "dark" ? t("common.themeDark") : t("common.themeLight")}
                        onPress={toggleTheme}
                        style={({ pressed }) => [
                            ProfileScreenStyles.preferenceChip,
                            ProfileScreenStyles.themeModeChip,
                            pressed && ProfileScreenStyles.preferenceChipPressed,
                        ]}
                    >
                        <Text style={ProfileScreenStyles.preferenceChipText}>
                            {themeName === "dark" ? t("common.themeDark") : t("common.themeLight")}
                        </Text>
                    </Pressable>
                </View>
                <Text style={ProfileScreenStyles.detailLabel}>{accentLabel}</Text>
                <View style={ProfileScreenStyles.colorSwatchRow}>
                    {accentOptions.map((accentOption) => (
                        <Pressable
                            key={accentOption}
                            accessibilityRole="button"
                            accessibilityLabel={accentOption}
                            onPress={() => setAccentName(accentOption)}
                            style={({ pressed }) => [
                                ProfileScreenStyles.colorSwatchShell,
                                accentName === accentOption && ProfileScreenStyles.colorSwatchShellActive,
                                pressed && ProfileScreenStyles.preferenceChipPressed,
                            ]}
                        >
                            <View
                                style={[
                                    ProfileScreenStyles.colorSwatch,
                                    { backgroundColor: themeAccentPalettes[accentOption].primary },
                                ]}
                            />
                        </Pressable>
                    ))}
                </View>
            </View>

            <View style={ProfileScreenStyles.sectionCard}>
                <Text style={ProfileScreenStyles.sectionTitle}>{t("profile.referral.attachCodeLabel")}</Text>
                {shouldShowReferralDetails && referralProfile?.promo_code ? (
                    <View style={ProfileScreenStyles.detailStack}>
                        <Text style={ProfileScreenStyles.sectionDescription}>
                            {t("profile.referral.attachedHint")}
                        </Text>
                        <View style={ProfileScreenStyles.detailRow}>
                            <Text style={ProfileScreenStyles.detailLabel}>{t("profile.referral.referrerPromo")}</Text>
                            <Text style={ProfileScreenStyles.detailValue}>
                                {referralProfile.promo_code}
                            </Text>
                        </View>
                        <Pressable
                            accessibilityLabel={t("profile.referral.detachAction")}
                            accessibilityRole="button"
                            disabled={isDetachingProfilePromo}
                            onPress={() => {
                                void handleDetachProfilePromo()
                            }}
                            style={({ pressed }) => [
                                ProfileScreenStyles.secondaryInlineButton,
                                pressed && !isDetachingProfilePromo && ProfileScreenStyles.secondaryInlineButtonPressed,
                                isDetachingProfilePromo && ProfileScreenStyles.primaryActionButtonDisabled,
                            ]}
                        >
                            <Text style={ProfileScreenStyles.secondaryInlineButtonText}>
                                {isDetachingProfilePromo
                                    ? t("profile.referral.detachLoading")
                                    : t("profile.referral.detachAction")}
                            </Text>
                        </Pressable>
                    </View>
                ) : (
                    <>
                        <Text style={ProfileScreenStyles.sectionDescription}>{t("profile.referral.attachHint")}</Text>
                        <View style={ProfileScreenStyles.formGroup}>
                            <TextInput
                                autoCapitalize="characters"
                                autoCorrect={false}
                                onChangeText={setProfilePromoCode}
                                placeholder={t("profile.referral.attachCodePlaceholder")}
                                placeholderTextColor="#94A3B8"
                                style={ProfileScreenStyles.formInput}
                                value={profilePromoCode}
                            />
                        </View>
                    </>
                )}
            </View>

            <View style={ProfileScreenStyles.sectionCard}>
                <View style={ProfileScreenStyles.sectionHeader}>
                    <View style={ProfileScreenStyles.sectionHeaderCopy}>
                        <Text style={ProfileScreenStyles.sectionTitle}>{t("profile.discounts.title")}</Text>
                        <Text style={ProfileScreenStyles.sectionDescription}>
                            {t("profile.discounts.subtitle")}
                        </Text>
                    </View>
                </View>

                {promotions.length ? (
                    <View style={ProfileScreenStyles.discountStack}>
                        {promotions.map((promotion) => (
                                <Pressable
                                    accessibilityLabel={`${promotion.title}, ${formatProfilePercent(promotion.discount_percent)}`}
                                    accessibilityRole="button"
                                    key={getProfilePromotionKey(promotion)}
                                    onPress={() => handleOpenPromotion(promotion)}
                                    style={({ pressed }) => [
                                        ProfileScreenStyles.discountRow,
                                        pressed && ProfileScreenStyles.discountRowPressed,
                                    ]}
                                >
                                    <Image
                                        resizeMode="cover"
                                        source={{ uri: promotion.image_url }}
                                        style={ProfileScreenStyles.discountImage}
                                    />
                                    <View style={ProfileScreenStyles.discountCopy}>
                                        <Text style={ProfileScreenStyles.discountTitle}>
                                            {promotion.title}
                                        </Text>
                                        <Text numberOfLines={2} style={ProfileScreenStyles.discountCode}>
                                            {promotion.kind === "category"
                                                ? t("profile.discounts.category")
                                                : t("profile.discounts.product")}
                                        </Text>
                                    </View>
                                    <View style={ProfileScreenStyles.discountBadge}>
                                        <Text style={ProfileScreenStyles.discountValue}>
                                            −{formatProfilePercent(promotion.discount_percent)}
                                        </Text>
                                    </View>
                                    <Text style={ProfileScreenStyles.discountArrow}>{">"}</Text>
                                </Pressable>
                        ))}
                    </View>
                ) : (
                    <Text style={ProfileScreenStyles.sectionDescription}>
                        {t("profile.discounts.empty")}
                    </Text>
                )}
            </View>

            {referralProfile ? (
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
                            <Text style={ProfileScreenStyles.metricLabel}>{t("profile.referral.bonusRubles")}</Text>
                            <Text style={ProfileScreenStyles.metricValue}>
                                {formatProfileMoney(referralProfile.bonus_rubles)}
                            </Text>
                        </View>
                        <View style={[ProfileScreenStyles.metricCard, { flexBasis: "47%", flexGrow: 1 }]}>
                            <Text style={ProfileScreenStyles.metricLabel}>{t("profile.referral.currentDiscount")}</Text>
                            <Text style={ProfileScreenStyles.metricValue}>
                                {formatProfilePercent(referralProfile.current_discount_percent)}
                            </Text>
                        </View>
                    </View>

                    <View style={ProfileScreenStyles.detailStack}>
                        <View style={ProfileScreenStyles.detailRow}>
                            <Text style={ProfileScreenStyles.detailLabel}>{t("profile.referral.discountBase")}</Text>
                            <Text style={ProfileScreenStyles.detailValue}>
                                {formatProfileMoney(referralProfile.referral_discount_base_total)}
                            </Text>
                        </View>
                        <View style={ProfileScreenStyles.detailDivider} />
                        <View style={ProfileScreenStyles.detailRow}>
                            <Text style={ProfileScreenStyles.detailLabel}>{t("profile.referral.referrerPromo")}</Text>
                            <Text style={ProfileScreenStyles.detailValue}>
                                {referralProfile.promo_code ?? "—"}
                            </Text>
                        </View>
                        <View style={ProfileScreenStyles.detailDivider} />
                        <View style={ProfileScreenStyles.detailRow}>
                            <Text style={ProfileScreenStyles.detailLabel}>{t("profile.referral.bonusPoints")}</Text>
                            <Text style={ProfileScreenStyles.detailValue}>
                                {new Intl.NumberFormat("ru-RU").format(referralProfile.bonus_points)}
                            </Text>
                        </View>
                    </View>
                </View>
            ) : null}

            <Pressable
                accessibilityLabel={t("nav.favorites")}
                accessibilityRole="button"
                onPress={() => router.push(ROUTES.favorites)}
                style={({ pressed }) => [
                    ProfileScreenStyles.historyCardButton,
                    pressed && ProfileScreenStyles.historyCardButtonPressed,
                ]}
            >
                <View style={ProfileScreenStyles.sectionCard}>
                    <View style={ProfileScreenStyles.historyCardHeader}>
                        <View style={ProfileScreenStyles.historyCardCopy}>
                            <Text style={ProfileScreenStyles.historyCardTitle}>{t("route.favorites")}</Text>
                            <Text style={ProfileScreenStyles.historyCardSubtitle}>{t("nav.favorites")}</Text>
                        </View>

                        <Text style={ProfileScreenStyles.historyCardArrow}>
                            {">"}
                        </Text>
                    </View>
                </View>
            </Pressable>

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

            <ProfileQuickActions
                isDeletingAccount={isDeletingAccount}
                onDeleteAccount={handleDeleteAccount}
                onSignOut={handleSignOut}
            />
        </FeedTemplate>
    )
}
