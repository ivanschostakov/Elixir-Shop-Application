import { useRef, useState } from "react"
import { ActivityIndicator, Image, Modal, Pressable, ScrollView, Text, TextInput, View } from "react-native"
import { router, type Href } from "expo-router"

import { getProductRoute, ROUTES } from "@/constants/routes"
import { useAsyncData } from "@/hooks/shared/use-async-data"
import { useAppSafeAreaInsets } from "@/hooks/use-app-safe-area-insets"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { getTranslationLocale } from "@/i18n/translations"
import { partnerOfferBody } from "@/i18n/loyalty"
import { useAuth } from "@/providers/auth-provider"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import { discountsIcons } from "@/screens/profile/discounts-menu-assets"
import { createProfileDiscountsScreenStyles } from "@/screens/profile/profile-discounts-screen.styles"
import { getMyAppRewards } from "@/services/api/benefits"
import type { AppRewardsResponse } from "@/services/api/benefits.types"
import type { SettlementResponse } from "@/services/api/settlement"
import { bindMyReferrerCode, detachMyReferrerCode, getMyPromotions } from "@/services/api/users"
import { confirmPromoBinding } from "@/screens/cart/confirm-promo-binding"
import { getErrorMessage } from "@/utils/errors"
import { createUuid } from "@/utils/uuid"
import type { ProfilePromotionResponse } from "@/services/api/users.types"
import { formatSettlementMoney } from "@/utils/settlement"

export type DiscountSection = "offers" | "reviews" | "terms" | "codes" | "welcome"

type DetailsProps = {
    section: DiscountSection
    account: SettlementResponse | null
    accountStatus: string | null
    userId: number
    onClose: () => void
    onUnlinked: () => void
    onBound: (code: string) => void
}

export function DiscountsDetails({ section, account, accountStatus, userId, onClose, onUnlinked, onBound }: DetailsProps) {
    const styles = useThemeStyles(createProfileDiscountsScreenStyles)
    const { milestones } = useAuth()
    const ownCode = milestones?.data?.own_promo_code ?? account?.own_promo_code
    const { t } = useLanguage()
    const { palette, accentPalette } = useTheme()
    const { bottom } = useAppSafeAreaInsets()
    const [confirm, setConfirm] = useState<{ step: 1 | 2; code: string; id: string } | null>(null)
    const [busy, setBusy] = useState(false)
    const [notice, setNotice] = useState("")
    const [entry, setEntry] = useState("")
    const submitting = useRef(false)
    const offers = useAsyncData<ProfilePromotionResponse[]>({
        deps: [userId], enabled: section === "offers", fetcher: getMyPromotions, initialData: [], showErrorAlert: false,
    })
    const rewards = useAsyncData<AppRewardsResponse | null>({
        deps: [userId], enabled: section === "welcome" || section === "reviews", fetcher: getMyAppRewards, initialData: null, showErrorAlert: false,
    })
    const resource = section === "offers" ? offers : rewards
    function openRoute(href: Href) {
        onClose()
        router.push(href)
    }

    function cancel() {
        if (!submitting.current) setConfirm(null)
    }
    async function bind() {
        const code = entry.trim()
        if (!code || submitting.current || account?.status !== "fresh" || account.referrer_promo_code) return
        submitting.current = true
        setBusy(true)
        setNotice("")
        try {
            if (!await confirmPromoBinding(t("cart.applyPromoCode"),
                t("cart.confirmPartnerOrder").replace("{code}", code), t("common.cancel"))) return
            const result = await bindMyReferrerCode(code)
            setEntry("")
            onBound(result.referrer_promo_code)
        } catch (error) {
            setNotice(getErrorMessage(error, t("cart.promoCodeUnavailableMessage")))
        } finally {
            setBusy(false)
            submitting.current = false
        }
    }
    async function unlink() {
        if (confirm?.step !== 2 || submitting.current) return
        submitting.current = true
        setBusy(true)
        try {
            await detachMyReferrerCode(confirm.code, confirm.id)
            onUnlinked()
            setNotice(t("profile.referral.detachSuccessTitle") + ". " + t("profile.referral.detachSuccessMessage"))
        } catch (error) {
            setNotice(getErrorMessage(error, t("profile.referral.detachFailed")))
        } finally {
            setConfirm(null)
            setBusy(false)
            submitting.current = false
        }
    }

    // Keep one native modal mounted: presenting a second iOS modal while the first
    // is dismissing can drop the irreversible-loss confirmation.
    if (confirm?.step) return <Modal visible transparent animationType="fade" onRequestClose={cancel}>
        <View style={[styles.modalBackdrop, styles.confirmBackdrop]}>
            <Pressable accessible={false} style={styles.dismissArea} onPress={cancel} />
            <ScrollView accessibilityViewIsModal onAccessibilityEscape={cancel} style={styles.confirmBox} contentContainerStyle={styles.confirmBody}>
                <Text key={confirm.step} accessibilityRole="header" accessibilityLiveRegion="assertive" style={styles.detailTitle}>
                    {t(confirm.step === 1 ? "profile.referral.detachConfirmTitle" : "profile.referral.detachLossTitle")}</Text>
                <Text style={styles.body}>{t(confirm.step === 1 ? "profile.referral.detachConfirmMessage" : "profile.referral.detachLossMessage").replace("{code}", confirm.code)}</Text>
                <Pressable accessibilityRole="button" disabled={busy} style={styles.action} onPress={cancel}>
                    <Text style={styles.actionLabel}>{t("common.cancel")}</Text>
                </Pressable>
                <Pressable key={confirm.step} accessibilityRole="button" disabled={busy} style={styles.action}
                    onPress={confirm.step === 1 ? () => setConfirm({ ...confirm, step: 2 }) : unlink}>
                    <Text style={[styles.actionLabel, confirm.step === 2 && { color: palette.danger }]}>{t(busy ? "profile.referral.detachLoading"
                        : confirm.step === 1 ? "payment.continue" : "profile.referral.detachAction")}</Text>
                </Pressable>
            </ScrollView>
        </View>
    </Modal>

    return <Modal visible transparent animationType="fade" onRequestClose={onClose}>
        <View style={styles.modalBackdrop}>
            <Pressable accessible={false} importantForAccessibility="no" onPress={onClose} style={styles.dismissArea} />
            <View accessibilityViewIsModal onAccessibilityEscape={onClose} style={[styles.sheet, { paddingBottom: Math.max(bottom, 12) }]}>
                <View style={styles.sheetHeader}>
                    <Text accessibilityRole="header" style={styles.sheetTitle}>{t(`profile.discounts.${section}`)}</Text>
                    <Pressable accessibilityRole="button" accessibilityLabel={t("common.close")} onPress={onClose} style={styles.iconButton}>
                        <Image accessible={false} source={discountsIcons.close} style={{ width: 17, height: 17, tintColor: palette.mutedText }} />
                    </Pressable>
                </View>
                <ScrollView contentContainerStyle={styles.sheetBody}>
                    {section === "terms" && <>
                        <Text style={styles.body}>{t("profile.discounts.balanceHint")}</Text>
                        {([1, 2] as const).map(id => {
                            const selected = account?.loyalty_program === id
                            return <View key={id} testID={`loyalty-program-${id}`} accessibilityState={{ selected }}
                                style={[styles.detailCard, selected && { borderColor: accentPalette.primary }]}>
                                <Text style={styles.detailTitle}>{t(id === 1 ? "profile.referral.bonusProgramTitle" : "profile.referral.partnerProgramTitle")}</Text>
                                {selected && <Text style={styles.rowSubtitle}>{t("profile.discounts.programSelected")}</Text>}
                                <Text style={styles.value}>{id === 1 ? "5%" : "3–20%"}</Text>
                                <Text style={styles.body}>{t(id === 1 ? "profile.discounts.guideCashbackText" : "profile.discounts.guidePromoText")}</Text>
                                {id === 2 && <Text style={styles.body}>{t("profile.discounts.programRangeHint")}</Text>}
                            </View>
                        })}
                        {account?.loyalty_program === 2 && !milestones?.data?.offer_partner &&
                            <Text style={styles.body}>{t("profile.referral.programLockedHint")}</Text>}
                    </>}
                    {(section === "terms" || section === "codes") && accountStatus && <Text style={styles.body}>{accountStatus}</Text>}
                    {(section === "terms" || section === "codes") && milestones && <>
                        {milestones.data?.offer_partner && <View style={styles.detailCard}>
                            <Text style={styles.detailTitle}>{t("milestone.offerTitle")}</Text>
                            <Text style={styles.body}>{partnerOfferBody(milestones.data.company_promo_code)}</Text>
                            <Pressable accessibilityRole="button" disabled={!!milestones.pending} style={styles.action}
                                onPress={() => void milestones.accept()}>
                                <Text style={styles.actionLabel}>{t("milestone.accept")}</Text>
                            </Pressable>
                        </View>}
                        {!!milestones.pending && <ActivityIndicator accessibilityLabel={t("common.loading")} />}
                        {milestones.error && <>
                            <Text accessibilityLiveRegion="polite" style={styles.body}>{t(milestones.error === "accept" ? "milestone.acceptFailed" : "milestone.checkFailed")}</Text>
                            <Pressable accessibilityRole="button" onPress={() => void milestones.check()} style={styles.action}>
                                <Text style={styles.actionLabel}>{t("common.retry")}</Text>
                            </Pressable>
                        </>}
                    </>}
                    {section === "codes" && <>
                        {!!notice && <Text accessibilityLiveRegion="polite" style={styles.body}>{notice}</Text>}
                        {account?.referrer_promo_code ? <View style={styles.detailCard}>
                            <Text style={styles.rowSubtitle}>{t("profile.referral.attachedPromo")}</Text>
                            <Text selectable style={styles.value}>{account.referrer_promo_code}</Text>
                            {account.status === "fresh" && !accountStatus && <Pressable accessibilityRole="button" style={styles.action}
                                onPress={() => { setNotice(""); setConfirm({ step: 1, code: account.referrer_promo_code!, id: createUuid() }) }}>
                                <Text style={[styles.actionLabel, { color: palette.danger }]}>{t("profile.referral.detachAction")}</Text>
                            </Pressable>}
                        </View> : !accountStatus && account?.status === "fresh" && <View style={styles.detailCard}>
                            <Text style={styles.body}>{t("profile.discounts.noAttachedPromo")}</Text>
                            <TextInput value={entry} onChangeText={setEntry} editable={!busy}
                                accessibilityLabel={t("cart.promoCodePlaceholder")} placeholder={t("cart.promoCodePlaceholder")}
                                placeholderTextColor={palette.mutedText} autoCapitalize="none" autoCorrect={false}
                                style={styles.promoInput} returnKeyType="done" onSubmitEditing={() => void bind()} />
                            <Pressable accessibilityRole="button" disabled={busy || !entry.trim()} onPress={bind}
                                style={[styles.action, (busy || !entry.trim()) && styles.pressed]}>
                                {busy ? <ActivityIndicator /> : <Text style={styles.actionLabel}>{t("profile.referral.attachAction")}</Text>}
                            </Pressable>
                        </View>}
                        {!!ownCode && <View style={styles.detailCard}>
                            <Text style={styles.rowSubtitle}>{t("profile.referral.ownPromo")}</Text>
                            <Text selectable style={styles.value}>{ownCode}</Text>
                        </View>}
                    </>}

                    {section === "offers" && <>
                        {!offers.loading && !offers.error && !offers.data.length &&
                            <Text style={styles.body}>{t("profile.discounts.empty")}</Text>}
                        {offers.data.map(promotion => <Pressable key={`${promotion.kind}-${promotion.category_id ?? promotion.product_id}-${promotion.product_id}`}
                            accessibilityRole="button" onPress={() => openRoute(promotion.kind === "category" && promotion.category_id
                                ? { pathname: ROUTES.discover, params: { categoryId: String(promotion.category_id) } }
                                : getProductRoute(promotion.product_id))}
                            style={({ pressed }) => [styles.offer, pressed && styles.pressed]}>
                            <Image accessible={false} resizeMode="contain" source={{ uri: promotion.image_url }} style={styles.offerImage} />
                            <View style={styles.offerCopy}>
                                <Text style={styles.rowTitle}>{promotion.title}</Text>
                                <Text style={styles.rowSubtitle}>{t(promotion.kind === "category" ? "profile.discounts.category" : "profile.discounts.product")}</Text>
                            </View>
                            <Text style={styles.detailTitle}>−{Number(promotion.discount_percent)}%</Text>
                        </Pressable>)}
                    </>}

                    {section === "reviews" && <>
                        <Text style={styles.body}>{t("profile.discounts.reviewHint")}</Text>
                        {rewards.data && <View style={styles.detailCard}>
                            <Text style={styles.rowTitle}>{t("profile.discounts.textReview")} · +{rewards.data.text_review_points}</Text>
                            <Text style={styles.rowTitle}>{t("profile.discounts.photoReview")} · +{rewards.data.photo_review_points}</Text>
                        </View>}
                        <Pressable accessibilityRole="button" onPress={() => openRoute(ROUTES.discover)}
                            style={({ pressed }) => [styles.action, pressed && styles.pressed]}>
                            <Text style={styles.actionLabel}>{t("profile.discounts.findProduct")}</Text>
                        </Pressable>
                    </>}

                    {section === "welcome" && <>
                        <Text style={styles.body}>{t("profile.discounts.welcomeHint")}</Text>
                        {rewards.data && <View style={styles.detailCard}>
                            <Text style={styles.rowSubtitle}>{t("profile.discounts.balance")}</Text>
                            <Text style={styles.value}>{formatSettlementMoney(rewards.data.welcome_balance_rubles, 0)}</Text>
                            {Number(rewards.data.welcome_balance_rubles) > 0 && rewards.data.welcome_expires_at &&
                                <Text style={styles.body}>{t("profile.discounts.expires")} {new Date(rewards.data.welcome_expires_at).toLocaleString(getTranslationLocale(), {dateStyle: "medium", timeStyle: "short"})}</Text>}
                        </View>}
                    </>}
                    {(section === "offers" || section === "reviews" || section === "welcome") && <>
                        {resource.loading && <ActivityIndicator accessibilityLabel={t("common.loading")} color={accentPalette.primary} />}
                        {resource.error && <><Text style={styles.body}>{t("profile.settlement.unavailable")}</Text>
                            <Pressable accessibilityRole="button" onPress={() => void resource.reload()} style={styles.action}>
                                <Text style={styles.actionLabel}>{t("common.retry")}</Text>
                            </Pressable></>}
                    </>}
                </ScrollView>
            </View>
        </View>
    </Modal>
}
