import { useCallback, useRef } from "react"
import { ActivityIndicator, Image, Pressable, StyleSheet, Text, View } from "react-native"
import { router, useFocusEffect } from "expo-router"

import { FeedTemplate } from "@/components/templates/feed-template"
import { getProductRoute, ROUTES } from "@/constants/routes"
import { useAsyncData } from "@/hooks/shared/use-async-data"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useAuth } from "@/providers/auth-provider"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import { getMySettlement, type SettlementResponse } from "@/services/api/settlement"
import { getMyPromotions } from "@/services/api/users"
import type { ProfilePromotionResponse } from "@/services/api/users.types"
import type { ThemePalette } from "@/theme/colors"
import { formatSettlementMoney, settlementProgramKey } from "@/utils/settlement"

export default function ProfileSettlementScreen() {
    const { user } = useAuth()
    // Remount on account change so a failed request cannot retain another user's data.
    return user ? <AccountView key={user.id} userId={user.id} /> : null
}

function AccountView({ userId }: { userId: number }) {
    const styles = useThemeStyles(createStyles)
    const { t, language } = useLanguage()
    const { accentPalette } = useTheme()
    const lastGood = useRef<SettlementResponse | null>(null)
    const fetchSettlement = useCallback(async () => {
        const next = await getMySettlement()
        if (next.fetched_at) lastGood.current = next
        if (!next.fetched_at && next.status !== "unlinked" && lastGood.current) {
            return { ...lastGood.current, status: "stale" as const, issue: next.issue }
        }
        if (next.status === "unlinked") lastGood.current = null
        return next
    }, [])
    const { data, loading, error, reload } = useAsyncData<SettlementResponse | null>({
        deps: [userId], fetcher: fetchSettlement, initialData: null,
        preserveDataOnError: true,
    })
    const { data: promotions } = useAsyncData<ProfilePromotionResponse[]>({
        deps: [userId], fetcher: getMyPromotions, initialData: [],
    })
    const focusedOnce = useRef(false)
    useFocusEffect(useCallback(() => {
        if (!focusedOnce.current) {
            focusedOnce.current = true
            return
        }
        void reload({ showLoading: false })
    }, [reload]))

    const stale = Boolean(error || data?.status === "stale")
    const statusText = error
        ? t(data?.fetched_at ? "profile.settlement.stale" : "profile.settlement.unavailable")
        : data?.status === "unlinked"
            ? t("profile.settlement.unlinked")
            : data?.status === "unavailable"
                ? t("profile.settlement.unavailable")
                : stale ? t("profile.settlement.stale") : null
    const updated = data?.fetched_at ? new Date(data.fetched_at) : null
    const updatedText = updated && !Number.isNaN(updated.getTime())
        ? updated.toLocaleString(language === "en" ? "en-GB" : language === "kz" ? "kk-KZ" : "ru-RU")
        : null

    return (
        <FeedTemplate contentContainerStyle={styles.content} style={styles.screen}>
            <View style={styles.header}>
                <Text style={styles.heading}>{t("profile.settlement.balance")}</Text>
                <Pressable
                    accessibilityRole="button"
                    accessibilityLabel={t("profile.settlement.refresh")}
                    disabled={loading}
                    onPress={() => void reload()}
                    style={({ pressed }) => [styles.refresh, pressed && styles.pressed]}
                >
                    {loading ? <ActivityIndicator color={accentPalette.primary} /> : <Text style={styles.refreshText}>↻</Text>}
                </Pressable>
            </View>
            <View style={styles.balanceBand}>
                <Text style={styles.balance} adjustsFontSizeToFit minimumFontScale={0.5} numberOfLines={1}>
                    {formatSettlementMoney(data?.balance_rubles)}
                </Text>
                {data?.balance_rubles != null && Number(data.balance_rubles) < 0 ? (
                    <Text style={styles.warning}>{t("profile.settlement.debt")}</Text>
                ) : null}
                {statusText ? <Text accessibilityRole="alert" style={styles.warning}>{statusText}</Text> : null}
                {updatedText ? <Text style={styles.muted}>{t("profile.settlement.updated")}: {updatedText}</Text> : null}
            </View>
            <View style={styles.row}>
                <Text style={styles.label}>{t("profile.settlement.purchases")}</Text>
                <Text style={styles.value}>{formatSettlementMoney(data?.total_purchases_rubles)}</Text>
            </View>
            <View style={styles.row}>
                <Text style={styles.label}>{t("profile.settlement.program")}</Text>
                <Text style={styles.value}>{t(settlementProgramKey(data?.loyalty_program ?? null))}</Text>
            </View>
            {data?.own_promo_code ? (
                <View style={styles.row}>
                    <Text style={styles.label}>{t("profile.referral.ownPromo")}</Text>
                    <Text selectable style={styles.value}>{data.own_promo_code}</Text>
                </View>
            ) : null}
            {data?.referrer_promo_code ? (
                <View style={styles.row}>
                    <Text style={styles.label}>{t("profile.referral.attachedPromo")}</Text>
                    <Text selectable style={styles.value}>{data.referrer_promo_code}</Text>
                </View>
            ) : null}
            {promotions.length ? <Text style={styles.heading}>{t("profile.discounts.offersTitle")}</Text> : null}
            {promotions.map((promotion) => (
                <Pressable
                    accessibilityRole="button"
                    key={`${promotion.kind}-${promotion.category_id ?? promotion.product_id}`}
                    onPress={() => promotion.kind === "category" && promotion.category_id
                        ? router.push({ pathname: ROUTES.discover, params: { tab: "products", categoryId: String(promotion.category_id) } })
                        : router.push(getProductRoute(promotion.product_id))}
                    style={({ pressed }) => [styles.offer, pressed && styles.pressed]}
                >
                    <Image resizeMode="contain" source={{ uri: promotion.image_url }} style={styles.image} />
                    <Text style={styles.offerTitle}>{promotion.title}</Text>
                    <Text style={styles.offerDiscount}>{promotion.discount_percent}%</Text>
                </Pressable>
            ))}
        </FeedTemplate>
    )
}

const createStyles = (colors: ThemePalette) => StyleSheet.create({
    screen: { flex: 1, backgroundColor: colors.surface },
    content: { padding: 20, paddingBottom: 36, gap: 16, maxWidth: 760, width: "100%", alignSelf: "center" },
    header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 },
    heading: { fontSize: 20, lineHeight: 26, fontWeight: "700", color: colors.text, flexShrink: 1 },
    refresh: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
    refreshText: { fontSize: 28, color: colors.primary },
    pressed: { opacity: 0.65 },
    balanceBand: { gap: 8, paddingBottom: 20, borderBottomWidth: 1, borderColor: colors.border },
    balance: { fontSize: 36, lineHeight: 46, minHeight: 46, fontWeight: "700", color: colors.text },
    warning: { fontSize: 14, lineHeight: 20, color: colors.warning },
    muted: { fontSize: 13, lineHeight: 19, color: colors.mutedText },
    row: { gap: 6, paddingBottom: 16, borderBottomWidth: 1, borderColor: colors.border },
    label: { fontSize: 14, lineHeight: 20, color: colors.mutedText },
    value: { fontSize: 18, lineHeight: 26, fontWeight: "600", color: colors.text, flexShrink: 1 },
    offer: { flexDirection: "row", gap: 12, alignItems: "center", paddingVertical: 10 },
    image: { width: 60, height: 60, borderRadius: 6 },
    offerTitle: { flex: 1, fontSize: 15, lineHeight: 21, color: colors.text },
    offerDiscount: { fontSize: 15, fontWeight: "600", color: colors.success },
})
