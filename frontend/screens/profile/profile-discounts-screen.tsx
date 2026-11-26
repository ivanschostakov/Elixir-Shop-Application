import { Fragment, useCallback, useRef, useState } from "react"
import { ActivityIndicator, Image, Pressable, Text, useWindowDimensions, View } from "react-native"
import { router, useFocusEffect } from "expo-router"

import { FeedTemplate } from "@/components/templates/feed-template"
import { ROUTES } from "@/constants/routes"
import { useAsyncData } from "@/hooks/shared/use-async-data"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useAuth } from "@/providers/auth-provider"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import { discountsHero, discountsIcons } from "@/screens/profile/discounts-menu-assets"
import { DiscountsDetails, type DiscountSection } from "@/screens/profile/discounts-details"
import { createProfileDiscountsScreenStyles } from "@/screens/profile/profile-discounts-screen.styles"
import { getMySettlement, type SettlementResponse } from "@/services/api/settlement"
import { formatSettlementMoney, settlementProgramKey } from "@/utils/settlement"

export default function ProfileDiscountsScreen() {
    const { user } = useAuth()
    return user ? <DiscountsView key={user.id} userId={user.id} /> : null
}

function DiscountsView({ userId }: { userId: number }) {
    const styles = useThemeStyles(createProfileDiscountsScreenStyles)
    const { t } = useLanguage()
    const { palette, accentPalette, isDark } = useTheme()
    const { width, fontScale } = useWindowDimensions()
    const [section, setSection] = useState<DiscountSection | null>(null)
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
        deps: [userId], fetcher: fetchAccount, initialData: null, preserveDataOnError: true, showErrorAlert: false,
    })
    const focusedOnce = useRef(false)
    useFocusEffect(useCallback(() => {
        if (!focusedOnce.current) { focusedOnce.current = true; return }
        void reload({ showLoading: false })
    }, [reload]))

    const program = data?.loyalty_program ?? null
    const programName = t(settlementProgramKey(program))
    const available = Boolean(data?.fetched_at)
    let status: string | null = null
    if (loading && !available) status = t("common.loading")
    else if (data?.status === "unlinked") status = t("profile.settlement.unlinked")
    else if (error || data?.status === "stale" || data?.status === "unavailable") {
        status = t(available ? "profile.settlement.stale" : "profile.settlement.unavailable")
    }
    const benefit = program === 1 ? t("checkout.rewardCashbackTitle").replace("{percent}", "5") : programName
    const benefitHint = program === 1 ? t("profile.discounts.afterShipment")
        : program === 2 ? t("profile.discounts.partnerHint")
        : t(program === 0 ? "profile.discounts.programNoneDescription" : "profile.discounts.programUnknownDescription")

    return <FeedTemplate contentContainerStyle={styles.content} style={styles.screen}>
        <Pressable accessibilityRole="button" onPress={() => router.dismissTo(ROUTES.profile)}
            style={({ pressed }) => [styles.back, pressed && styles.pressed]}>
            <Image accessible={false} source={discountsIcons.back} style={{ width: 15, height: 20, tintColor: accentPalette.primary }} resizeMode="contain" />
            <Text style={[styles.backLabel, { color: accentPalette.primary }]}>{t("route.profile")}</Text>
        </Pressable>
        <Text accessibilityRole="header" style={styles.title}>{t("profile.discounts.title")}</Text>
        <View testID="loyalty-balance" style={styles.hero}>
            <Image accessible={false} source={discountsHero} resizeMode="cover" style={styles.heroArt} />
            <View style={[styles.heroContent, { minHeight: Math.max(182, Math.min(240, (width - 32) / 2)) }]}>
                <View style={styles.heroAmount}>
                    <Text style={styles.heroLabel}>{t("profile.discounts.balance")}</Text>
                    <Text style={styles.balance} adjustsFontSizeToFit numberOfLines={1}>
                        {formatSettlementMoney(data?.balance_rubles, 0)}
                    </Text>
                </View>
                <View style={styles.heroFooter}>
                    <Pressable accessibilityRole="button" accessibilityLabel={t("profile.settlement.refresh")}
                        disabled={loading} onPress={() => void reload()} style={styles.iconButton}>
                        {loading ? <ActivityIndicator color="#FFFFFF" /> :
                            <Image accessible={false} source={discountsIcons.refresh} style={{ width: 25, height: 25, tintColor: "#FFFFFF" }} />}
                    </Pressable>
                    <View style={styles.heroCopy}>
                        <Text style={styles.heroBenefit}>{benefit}</Text>
                        <Text accessibilityLiveRegion="polite" style={styles.heroHint}>{status ?? benefitHint}</Text>
                    </View>
                </View>
            </View>
        </View>

        <View style={styles.shortcuts}>
            {(["offers", "reviews"] as const).map(key => {
                const offers = key === "offers"
                const backgroundColor = offers ? (isDark ? "#153351" : "#D9EDFF") : (isDark ? "#312748" : "#ECE6FF")
                const tintColor = offers ? (isDark ? "#87BEFF" : "#0969DB") : (isDark ? "#C9AAFF" : "#7335D1")
                return <Pressable key={key} accessibilityRole="button" onPress={() => setSection(key)}
                    style={({ pressed }) => [styles.shortcut, (width < 350 || fontScale > 1.25) && styles.shortcutNarrow, { backgroundColor }, pressed && styles.pressed]}>
                    <Image accessible={false} source={discountsIcons[key]} style={{ width: 28, height: 28, tintColor }} />
                    <Text style={styles.shortcutTitle}>{t(`profile.discounts.${key}`)}</Text>
                </Pressable>
            })}
        </View>

        <Text accessibilityRole="header" style={styles.sectionTitle}>{t("profile.discounts.myProgram")}</Text>
        <View style={styles.list}>
            {(["terms", "purchases", "codes", "welcome"] as const).map((key, index) => (
                <Fragment key={key}>
                    {index > 0 && <View style={styles.divider} />}
                    <Pressable accessibilityRole="button"
                        onPress={() => key === "purchases" ? router.push(ROUTES.profileHistory) : setSection(key)}
                        style={({ pressed }) => [styles.row, pressed && styles.pressed]}>
                        <Image accessible={false} source={discountsIcons[key]} style={{ width: 23, height: 23, tintColor: palette.text }} />
                        <View style={styles.rowCopy}>
                            <Text style={styles.rowTitle}>{t(`profile.discounts.${key}`)}</Text>
                            {key === "terms" && <Text style={styles.rowSubtitle}>{programName}</Text>}
                            {key === "purchases" && data?.total_purchases_rubles != null &&
                                <Text style={styles.rowSubtitle}>{t("profile.settlement.purchases")} · {formatSettlementMoney(data.total_purchases_rubles, 0)}</Text>}
                        </View>
                        <Image accessible={false} source={discountsIcons.next} style={{ width: 13, height: 13, tintColor: palette.mutedText }} />
                    </Pressable>
                </Fragment>
            ))}
        </View>
        {section && <DiscountsDetails section={section} account={data} accountStatus={status} userId={userId}
            onClose={() => setSection(null)} />}
    </FeedTemplate>
}
