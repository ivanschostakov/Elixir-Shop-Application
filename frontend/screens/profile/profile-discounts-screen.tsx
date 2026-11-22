import { useCallback, useRef } from "react"
import { ActivityIndicator, Image, Pressable, Text, View } from "react-native"
import { LinearGradient } from "expo-linear-gradient"
import { router, useFocusEffect } from "expo-router"

import { FeedTemplate } from "@/components/templates/feed-template"
import { getProductRoute, ROUTES } from "@/constants/routes"
import { useAsyncData } from "@/hooks/shared/use-async-data"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useAuth } from "@/providers/auth-provider"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import { createProfileDiscountsScreenStyles } from "@/screens/profile/profile-discounts-screen.styles"
import { getMySettlement, type SettlementResponse } from "@/services/api/settlement"
import { getMyPromotions } from "@/services/api/users"
import type { ProfilePromotionResponse } from "@/services/api/users.types"
import { formatSettlementMoney, settlementProgramKey } from "@/utils/settlement"

export default function ProfileDiscountsScreen() {
    const { user } = useAuth()
    return user ? <DiscountsView key={user.id} userId={user.id} /> : null
}

function DiscountsView({ userId }: { userId: number }) {
    const styles = useThemeStyles(createProfileDiscountsScreenStyles)
    const { t } = useLanguage()
    const { accentPalette, palette } = useTheme()
    const lastGood = useRef<SettlementResponse | null>(null)
    const fetchAccount = useCallback(async () => {
        const next = await getMySettlement()
        if (next.fetched_at) lastGood.current = next
        if (!next.fetched_at && next.status !== "unlinked" && lastGood.current) {
            return { ...lastGood.current, status: "stale" as const, issue: next.issue }
        }
        if (next.status === "unlinked") lastGood.current = null
        return next
    }, [])
    const { data, loading, error, reload } = useAsyncData<SettlementResponse | null>({
        deps: [userId], fetcher: fetchAccount, initialData: null, preserveDataOnError: true,
    })
    const { data: promotions, reload: reloadPromotions } = useAsyncData<ProfilePromotionResponse[]>({
        deps: [userId], fetcher: getMyPromotions, initialData: [], preserveDataOnError: true,
    })
    const focusedOnce = useRef(false)
    useFocusEffect(useCallback(() => {
        if (!focusedOnce.current) { focusedOnce.current = true; return }
        void reload({ showLoading: false })
        void reloadPromotions({ showLoading: false })
    }, [reload, reloadPromotions]))

    const program = data?.loyalty_program ?? null
    const bonusSelected = program === 1
    const partnerSelected = program === 2
    const available = Boolean(data?.fetched_at)
    const issue = error || data?.status === "stale" || data?.status === "unavailable" || data?.status === "unlinked"
    const summaryValue = bonusSelected ? "5%" : partnerSelected ? "3–20%" : "—"
    const programName = t(settlementProgramKey(program))
    const statusLabel = loading && !available
        ? t("common.loading")
        : issue ? t(available ? "profile.settlement.stale" : "profile.settlement.unavailable") : null

    return <FeedTemplate contentContainerStyle={styles.content} scrollViewStyle={styles.container} style={styles.screen}>
        <LinearGradient colors={[accentPalette.primary, accentPalette.primaryPressed]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.summaryCard}>
            <View style={styles.summaryGlow} />
            <View>
                <Text style={styles.summaryEyebrow}>{t("profile.discounts.selectedProgram")}</Text>
                <View style={styles.summaryValueRow}>
                    <Text style={styles.summaryValue}>{summaryValue}</Text>
                    <Text style={styles.summaryValueLabel}>{programName}</Text>
                </View>
                <Text style={styles.summaryDescription}>{t(bonusSelected ? "profile.discounts.guideCashbackText" : partnerSelected ? "profile.discounts.programRangeHint" : program === 0 ? "profile.discounts.programNoneDescription" : "profile.discounts.programUnknownDescription")}</Text>
            </View>
            <View style={styles.summaryMeta}>
                <Text style={styles.summaryMetaLabel}>{statusLabel ?? t(program === 0 ? "profile.settlement.programNone" : "profile.discounts.activeNow")}</Text>
                <Pressable accessibilityRole="button" accessibilityLabel={t("profile.settlement.refresh")} disabled={loading} onPress={() => { void reload(); void reloadPromotions() }} style={styles.refreshButton}>
                    {loading ? <ActivityIndicator color="#FFFFFF" /> : <Text style={styles.summaryMetaValue}>↻</Text>}
                </Pressable>
            </View>
        </LinearGradient>

        <View style={styles.card} testID="loyalty-balance">
            <View style={styles.statRow}>
                <Text style={styles.statLabel}>{t("profile.settlement.balance")}</Text>
                <Text style={styles.statValue}>{formatSettlementMoney(data?.balance_rubles)}</Text>
            </View>
            <Text style={styles.cardDescription}>{statusLabel ?? t(bonusSelected || partnerSelected ? "profile.discounts.balanceHint" : program === 0 ? "profile.discounts.programNoneDescription" : "profile.discounts.programUnknownDescription")}</Text>
        </View>

        <View style={styles.sectionHeading}>
            <Text style={styles.cardTitle}>{t("profile.discounts.allProgramsTitle")}</Text>
            <Text style={styles.cardDescription}>{t("profile.referral.programLockedHint")}</Text>
        </View>
        {([
            { id: 1, selected: bonusSelected, title: "profile.referral.bonusProgramTitle", value: "5%", description: "profile.discounts.guideCashbackText", rules: "profile.discounts.guideCashbackRules" },
            { id: 2, selected: partnerSelected, title: "profile.referral.partnerProgramTitle", value: "3–20%", description: "profile.discounts.guidePromoText", rules: "profile.discounts.guidePartnerRules" },
        ] as const).map(item => <View key={item.id} testID={`loyalty-program-${item.id}`} accessibilityState={{ selected: item.selected }} style={[styles.card, item.selected && { borderColor: accentPalette.primary, borderWidth: 1.5 }]}>
            <View style={styles.cardHeader}>
                <View style={styles.cardHeaderCopy}>
                    <Text style={styles.cardTitle}>{t(item.title)}</Text>
                    <Text style={[styles.programValue, { color: accentPalette.primary }]}>{item.value}</Text>
                </View>
                {item.selected ? <View style={[styles.activeBadge, { backgroundColor: accentPalette.primaryMuted }]}><Text style={[styles.activeBadgeText, { color: accentPalette.primary }]}>{t("profile.discounts.programSelected")}</Text></View> : null}
            </View>
            <Text style={styles.ruleText}>{t(item.description)}</Text>
            <View style={styles.ruleDivider} />
            <Text style={styles.ruleText}>{t(item.rules)}</Text>
            {item.id === 2 ? <Text style={styles.cardDescription}>{t("profile.discounts.progressOwnPromoHint")}</Text> : null}
        </View>)}

        <View style={styles.card}>
            <Text style={styles.cardTitle}>{t("profile.discounts.purchaseDetailsTitle")}</Text>
            <View style={styles.statRow}>
                <Text style={styles.statLabel}>{t("profile.referral.totalPurchases")}</Text>
                <Text style={styles.statValue}>{formatSettlementMoney(data?.total_purchases_rubles)}</Text>
            </View>
            <Text style={styles.cardDescription}>{t("profile.discounts.guidePartnerText")}</Text>
        </View>

        <View style={styles.card}>
            <Text style={styles.cardTitle}>{t("profile.discounts.promoTitle")}</Text>
            {data?.referrer_promo_code ? <View style={styles.promoSurface}>
                <View style={styles.promoCopy}><Text style={styles.smallLabel}>{t("profile.referral.attachedPromo")}</Text><Text selectable style={styles.promoCode}>{data.referrer_promo_code}</Text></View>
            </View> : <Text style={styles.cardDescription}>{t("profile.discounts.noAttachedPromo")}</Text>}
            {data?.own_promo_code ? <View style={styles.promoSurface}>
                <View style={styles.promoCopy}><Text style={styles.smallLabel}>{t("profile.referral.ownPromo")}</Text><Text selectable style={styles.promoCode}>{data.own_promo_code}</Text></View>
            </View> : null}
        </View>

        <View style={styles.card}>
            <Text style={styles.cardTitle}>{t("profile.discounts.offersTitle")}</Text>
            <Text style={styles.cardDescription}>{t("profile.discounts.subtitle")}</Text>
            {!promotions.length ? <Text style={styles.cardDescription}>{t("profile.discounts.empty")}</Text> : null}
            {promotions.map(promotion => <Pressable key={`${promotion.kind}-${promotion.category_id ?? promotion.product_id}`} accessibilityRole="button"
                onPress={() => promotion.kind === "category" && promotion.category_id
                    ? router.push({ pathname: ROUTES.discover, params: { categoryId: String(promotion.category_id) } })
                    : router.push(getProductRoute(promotion.product_id))}
                style={({ pressed }) => [styles.promotionRow, pressed && { opacity: 0.7 }]}>
                <Image resizeMode="contain" source={{ uri: promotion.image_url }} style={styles.promotionImage} />
                <View style={styles.promotionCopy}><Text style={styles.promotionTitle}>{promotion.title}</Text><Text style={styles.promotionSubtitle}>{t(promotion.kind === "category" ? "profile.discounts.category" : "profile.discounts.product")}</Text></View>
                <Text style={[styles.promotionDiscount, { color: palette.primary }]}>−{promotion.discount_percent}%</Text>
            </Pressable>)}
        </View>
    </FeedTemplate>
}
