import { useEffect, useMemo, useRef } from "react"
import { ActivityIndicator, Pressable, Text, View } from "react-native"
import { router } from "expo-router"
import { useIsFocused } from "@react-navigation/native"

import { ROUTES } from "@/constants/routes"
import { useAsyncData } from "@/hooks/shared/use-async-data"
import { useLanguage } from "@/providers/language-provider"
import {
    formatCouponValue,
    formatEntitlementValue,
    formatMoney,
} from "@/components/profile/profile-website-identity-card.utils"
import { colors } from "@/theme/colors"
import { ProfileScreenStyles } from "@/screens/profile/profile-screen.styles"
import { getMyWebsiteIdentity } from "@/services/api/website-identity"
import type { WebsiteIdentity } from "@/services/api/website-identity.types"

export function ProfileWebsiteIdentityCard() {
    const { t } = useLanguage()
    const isFocused = useIsFocused()
    const hasLoadedOnceRef = useRef(false)
    const {
        data: websiteIdentity,
        error,
        loading,
        reload,
    } = useAsyncData<WebsiteIdentity | null>({
        deps: [],
        enabled: false,
        fetcher: getMyWebsiteIdentity,
        initialData: null,
    })

    useEffect(() => {
        if (!isFocused) {
            return
        }

        void reload({ showLoading: !hasLoadedOnceRef.current }).finally(() => {
            hasLoadedOnceRef.current = true
        })
    }, [isFocused, reload])

    const activeEntitlements = useMemo(
        () => websiteIdentity?.discount_entitlements.filter((entitlement) => entitlement.is_active) ?? [],
        [websiteIdentity],
    )
    const activeCoupons = useMemo(
        () => websiteIdentity?.coupon_snapshots.filter((coupon) => coupon.is_active) ?? [],
        [websiteIdentity],
    )
    const bonusBalance = websiteIdentity?.bonus_account_snapshot
        ? formatMoney(websiteIdentity.bonus_account_snapshot.balance, websiteIdentity.bonus_account_snapshot.currency)
        : null

    return (
        <View style={ProfileScreenStyles.sectionCard}>
            <View style={ProfileScreenStyles.sectionHeader}>
                <View style={ProfileScreenStyles.sectionHeaderCopy}>
                    <Text style={ProfileScreenStyles.sectionTitle}>{t("profile.website.title")}</Text>
                    <Text style={ProfileScreenStyles.sectionDescription}>
                        {websiteIdentity ? t("profile.website.linkedSubtitleCompact") : t("profile.website.unlinkedSubtitleCompact")}
                    </Text>
                </View>

                <View
                    style={[
                        ProfileScreenStyles.statusBadge,
                        websiteIdentity ? ProfileScreenStyles.statusBadgeSuccess : ProfileScreenStyles.statusBadgeMuted,
                    ]}
                >
                    <Text
                        style={[
                            ProfileScreenStyles.statusBadgeText,
                            websiteIdentity ? ProfileScreenStyles.statusBadgeTextSuccess : ProfileScreenStyles.statusBadgeTextMuted,
                        ]}
                    >
                        {websiteIdentity ? t("profile.website.connected") : t("profile.website.notConnected")}
                    </Text>
                </View>
            </View>

            {loading ? (
                <View style={ProfileScreenStyles.loadingBox}>
                    <ActivityIndicator color={colors.primary} />
                </View>
            ) : null}

            {error ? (
                <View style={ProfileScreenStyles.errorBox}>
                    <Text style={ProfileScreenStyles.errorText}>{error}</Text>
                    <Pressable
                        onPress={() => void reload()}
                        style={({ pressed }) => [
                            ProfileScreenStyles.secondaryInlineButton,
                            pressed && ProfileScreenStyles.secondaryInlineButtonPressed,
                        ]}
                    >
                        <Text style={ProfileScreenStyles.secondaryInlineButtonText}>{t("profile.website.retry")}</Text>
                    </Pressable>
                </View>
            ) : null}

            {websiteIdentity ? (
                <>
                    <View style={ProfileScreenStyles.websiteChipRow}>
                        <View style={ProfileScreenStyles.websiteChip}>
                            <Text style={ProfileScreenStyles.websiteChipValue}>
                                {bonusBalance ?? t("profile.website.noBonusBalance")}
                            </Text>
                            <Text style={ProfileScreenStyles.websiteChipLabel}>{t("profile.website.bonusTitle")}</Text>
                        </View>

                        <View style={ProfileScreenStyles.websiteChip}>
                            <Text style={ProfileScreenStyles.websiteChipValue}>{activeEntitlements.length}</Text>
                            <Text style={ProfileScreenStyles.websiteChipLabel}>{t("profile.website.personalDiscounts")}</Text>
                        </View>

                        <View style={ProfileScreenStyles.websiteChip}>
                            <Text style={ProfileScreenStyles.websiteChipValue}>{activeCoupons.length}</Text>
                            <Text style={ProfileScreenStyles.websiteChipLabel}>{t("profile.website.activeCoupons")}</Text>
                        </View>
                    </View>

                    <View style={ProfileScreenStyles.subsection}>
                        <Text style={ProfileScreenStyles.subsectionTitle}>{t("profile.website.discountTitle")}</Text>
                        {activeEntitlements.length > 0 ? (
                            <View style={ProfileScreenStyles.tagList}>
                                {activeEntitlements.map((entitlement) => (
                                    <View key={entitlement.id} style={ProfileScreenStyles.tag}>
                                        <Text style={ProfileScreenStyles.tagTitle}>{entitlement.source_name}</Text>
                                        <Text style={ProfileScreenStyles.tagSubtitle}>
                                            {formatEntitlementValue(entitlement, t("profile.website.discountUnknown"))}
                                        </Text>
                                    </View>
                                ))}
                            </View>
                        ) : (
                            <Text style={ProfileScreenStyles.emptyHint}>{t("profile.website.noPersonalDiscounts")}</Text>
                        )}
                    </View>

                    <View style={ProfileScreenStyles.subsection}>
                        <Text style={ProfileScreenStyles.subsectionTitle}>{t("profile.website.couponTitle")}</Text>
                        {activeCoupons.length > 0 ? (
                            <View style={ProfileScreenStyles.tagList}>
                                {activeCoupons.map((coupon) => (
                                    <View key={coupon.id} style={ProfileScreenStyles.tag}>
                                        <Text style={ProfileScreenStyles.tagTitle}>{coupon.coupon_code}</Text>
                                        <Text style={ProfileScreenStyles.tagSubtitle}>
                                            {formatCouponValue(coupon, t("profile.website.discountUnknown"))}
                                        </Text>
                                    </View>
                                ))}
                            </View>
                        ) : (
                            <Text style={ProfileScreenStyles.emptyHint}>{t("profile.website.noCoupons")}</Text>
                        )}
                    </View>
                </>
            ) : (
                <>
                    <Text style={ProfileScreenStyles.emptyHint}>{t("profile.website.emptyStateCompact")}</Text>
                    <Pressable
                        onPress={() => router.push(ROUTES.websiteAccount)}
                        style={({ pressed }) => [
                            ProfileScreenStyles.primaryActionButton,
                            pressed && ProfileScreenStyles.primaryActionButtonPressed,
                        ]}
                    >
                        <Text style={ProfileScreenStyles.primaryActionButtonText}>{t("profile.website.connectAction")}</Text>
                    </Pressable>
                </>
            )}
        </View>
    )
}
