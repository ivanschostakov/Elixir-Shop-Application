import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react"
import {
    Alert,
    ActivityIndicator,
    type NativeScrollEvent,
    type NativeSyntheticEvent,
    Pressable,
    ScrollView,
    Text,
    TextInput,
    View,
} from "react-native"
import { router, useFocusEffect, useLocalSearchParams } from "expo-router"
import Swipeable from "react-native-gesture-handler/Swipeable"
import { Path, Svg } from "react-native-svg"

import { ContentRail } from "@/components/content/content-rail"
import { formatProductPrice } from "@/components/content/product-content"
import { EmptyState } from "@/components/content/empty-state"
import { createStickyFooterStyles } from "@/components/footer/sticky-footer.styles"
import { useApplyScreenTemplate } from "@/components/templates/screen-template.hooks"
import { getProductRoute, ROUTES } from "@/constants/routes"
import { STICKERS } from "@/constants/stickers"
import { useBasket } from "@/hooks/basket/use-basket"
import { useOrderBenefits } from "@/hooks/basket/use-order-benefits"
import {
    clearBasketDraftEditingId,
    setBasketDraftEditingId,
    useBasketDraftEditingId,
} from "@/hooks/basket/basket-draft-editing-store"
import { clearBasketSnapshot } from "@/hooks/basket/basket-store"
import { useBasketMutations } from "@/hooks/basket/use-basket-mutations"
import {
    useSelectedDeliveryAddress,
} from "@/hooks/delivery/delivery-address-selection-store"
import {
    useSelectedDeliveryCountry,
} from "@/hooks/delivery/delivery-country-selection-store"
import {
    useSelectedDeliveryPoint,
} from "@/hooks/delivery/delivery-point-selection-store"
import { setOrderDraftSnapshot } from "@/hooks/order-draft/order-draft-store"
import { useRecentOrderDrafts } from "@/hooks/order-draft/use-recent-order-drafts"
import { useInfiniteProductCatalog } from "@/hooks/products/use-infinite-product-catalog"
import { useRecommendations } from "@/hooks/recommendations/use-recommendations"
import { useAsyncData } from "@/hooks/shared/use-async-data"
import { useAuth } from "@/providers/auth-provider"
import { useLanguage } from "@/providers/language-provider"
import { CartBasketItem } from "@/screens/cart/cart-basket-item"
import { createCartScreenStyles } from "@/screens/cart/cart-screen.styles"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useTheme } from "@/providers/theme-provider"
import {
    buildOrderDraftCalculationPayload,
    buildPickupPointAddress,
    formatSavedCartDraftName,
    getBasketErrorMessage,
    getOrderDraftProvider,
} from "@/screens/cart/cart-screen.utils"
import { DOOR_DELIVERY_ENABLED } from "@/screens/delivery/delivery-screen.constants"
import { ApiError } from "@/services/api/client"
import { confirmPromoBinding } from "@/screens/cart/confirm-promo-binding"
import { createOrderDraft, updateOrderDraft } from "@/services/api/order-drafts"
import type { CreateOrderDraftPayload } from "@/services/api/order-drafts.types"
import { bindMyReferrerCode, getMyReferralProfile } from "@/services/api/users"
import { hasAppliedOrderPromo } from "@/screens/cart/order-promo"
import type { ReferralProfileResponse } from "@/services/api/users.types"
import type { BasketItemRead } from "@/types/basket"
import { formatAppliedDiscount } from "@/utils/discount-display"
import { getQuotedItemPrice } from "@/utils/quoted-item-price"

export default function CartScreen() {
    const stickyFooterStyles = useThemeStyles(createStickyFooterStyles)
    const cartScreenStyles = useThemeStyles(createCartScreenStyles)
    const { palette } = useTheme()
    const params = useLocalSearchParams<{ draftId?: string | string[] }>()
    const { t } = useLanguage()
    const { isAuthenticated, isReady, user, milestones } = useAuth()
    const { basket, error: basketLoadError, loading, reload } = useBasket()
    const { clear, error: basketActionError, removeItem, updateItemQuantity, updating } = useBasketMutations()
    const basketDraftEditingId = useBasketDraftEditingId()
    const selectedDeliveryAddress = useSelectedDeliveryAddress()
    const selectedDeliveryPoint = useSelectedDeliveryPoint()
    const selectedDeliveryCountry = useSelectedDeliveryCountry()
    const [promoCode, setPromoCode] = useState("")
    const [appliedPromoCode, setAppliedPromoCode] = useState<string | null>(null)
    const [isSavingDraft, setIsSavingDraft] = useState(false)
    const [isOpeningCheckout, setIsOpeningCheckout] = useState(false)
    const [isCheckingPromoCode, setIsCheckingPromoCode] = useState(false)
    const swipeableRefs = useRef<Record<number, Swipeable | null>>({})
    const routeDraftIdParam = Array.isArray(params.draftId) ? params.draftId[0] : params.draftId
    const { orderDrafts: recentOrderDrafts, loading: recentOrderDraftsLoading } = useRecentOrderDrafts(1, isAuthenticated)
    const {
        data: referralProfile,
        setData: setReferralProfile,
        error: referralError,
        reload: reloadReferralProfile,
    } = useAsyncData<ReferralProfileResponse | null>({
        deps: [user?.id ?? null, milestones?.programRevision],
        enabled: Boolean(isAuthenticated && basket?.items.length),
        fetcher: getMyReferralProfile,
        initialData: null,
        resetOnLoad: true,
    })
    const hasRecentOrderDrafts = isAuthenticated && recentOrderDrafts.length > 0
    const {
        hasMore: hasMoreRecommendations,
        loadMore: loadMoreRecommendations,
        loadingMore: recommendationsLoadingMore,
        products: recommendedProducts,
    } = useRecommendations({
        surface: "cart",
        limit: 6,
        enabled: Boolean(basket?.items.length),
        deps: [basket?.updated_at ?? null, basket?.items.length ?? 0],
    })
    const {
        hasMore: hasMoreGuestCatalog,
        loadMore: loadMoreGuestCatalog,
        loadingMore: guestCatalogLoadingMore,
        products: guestCatalogProducts,
    } = useInfiniteProductCatalog({
        enabled: Boolean(!isAuthenticated && basket?.items.length),
        pageSize: 6,
        sort: "newest",
    })
    const recommendationRailProducts = isAuthenticated ? recommendedProducts : guestCatalogProducts
    const recommendationRailLoadingMore = isAuthenticated ? recommendationsLoadingMore : guestCatalogLoadingMore
    const hasMoreRecommendationRail = isAuthenticated ? hasMoreRecommendations : hasMoreGuestCatalog
    const loadMoreRecommendationRail = isAuthenticated ? loadMoreRecommendations : loadMoreGuestCatalog
    const normalizedPromoCode = useMemo(() => {
        const trimmedCode = promoCode.trim()
        return trimmedCode ? trimmedCode : null
    }, [promoCode])
    const attachedPromoCode = referralProfile?.referrer_promo_code ?? null
    useEffect(() => {
        if (attachedPromoCode) {
            setPromoCode("")
            setAppliedPromoCode(null)
        }
    }, [attachedPromoCode])
    const programLocked = !referralProfile
    const hasAttachedPromoCode = Boolean(attachedPromoCode)
    const displayedPromoCode = attachedPromoCode ?? promoCode
    const hasUnappliedPromoCode = Boolean(isAuthenticated && !programLocked && !hasAttachedPromoCode && normalizedPromoCode && normalizedPromoCode !== appliedPromoCode)
    const activeEnteredPromoCode = !programLocked && !hasAttachedPromoCode ? appliedPromoCode : null
    const needsQuote = Boolean(isAuthenticated && basket?.items.length)
    const { data: benefitCheck, error: quoteError, reload: reloadQuote } = useOrderBenefits(
        [user?.id, milestones?.programRevision, attachedPromoCode, basket?.id, basket?.delivery_total, basket?.currency,
            basket?.items.map(item => [item.variant_id, item.quantity, item.line_total])],
        needsQuote && referralProfile !== null,
        { use_basket: true, code: activeEnteredPromoCode, reward_mode: activeEnteredPromoCode ? "order_referral" : undefined },
    )
    const pricingError = needsQuote && (referralError || quoteError)
    const waitingForPricing = needsQuote && !pricingError && !benefitCheck
    const pricingBlocked = Boolean(pricingError || waitingForPricing)

    useFocusEffect(
        useCallback(() => {
            if (basket?.items.length && isAuthenticated) {
                void reloadReferralProfile({ showLoading: false })
            }
        }, [basket?.items.length, isAuthenticated, reloadReferralProfile]),
    )

    useEffect(() => {
        const nextDraftId = routeDraftIdParam ? Number(routeDraftIdParam) : NaN
        const parsedDraftId = Number.isInteger(nextDraftId) && nextDraftId > 0 ? nextDraftId : null

        if (parsedDraftId !== null) {
            setBasketDraftEditingId(parsedDraftId)
            return
        }

        if (basketDraftEditingId !== null) {
            clearBasketDraftEditingId()
        }
    }, [basketDraftEditingId, routeDraftIdParam])

    const handleRemoveItem = async (itemId: number) => {
        try {
            swipeableRefs.current[itemId]?.close()
            await removeItem(itemId)
        } catch (error) {
            Alert.alert(getBasketErrorMessage(error, basketActionError, t))
        }
    }

    const handleConfirmRemoveItem = (itemId: number) => {
        Alert.alert(t("cart.removeConfirmTitle"), t("cart.removeConfirmMessage"), [
            {
                text: t("common.cancel"),
                style: "cancel",
            },
            {
                text: t("cart.removeItem"),
                style: "destructive",
                onPress: () => {
                    void handleRemoveItem(itemId)
                },
            },
        ])
    }

    const handleQuantityDecrease = async (item: BasketItemRead) => {
        if (item.quantity <= 1) {
            handleConfirmRemoveItem(item.id)
            return
        }

        try {
            await updateItemQuantity(item.id, item.quantity - 1)
        } catch (error) {
            Alert.alert(getBasketErrorMessage(error, basketActionError, t))
        }
    }

    const handleQuantityIncrease = async (item: BasketItemRead) => {
        if (item.quantity >= item.available_quantity) {
            return
        }

        try {
            await updateItemQuantity(item.id, item.quantity + 1)
        } catch (error) {
            Alert.alert(getBasketErrorMessage(error, basketActionError, t))
        }
    }

    const handleOpenProduct = (productId: number) => {
        router.push(getProductRoute(productId))
    }

    const handleRecommendationsScroll = useCallback((event: NativeSyntheticEvent<NativeScrollEvent>) => {
        if (!hasMoreRecommendationRail || recommendationRailLoadingMore) {
            return
        }

        const distanceFromBottom =
            event.nativeEvent.contentSize.height -
            (event.nativeEvent.contentOffset.y + event.nativeEvent.layoutMeasurement.height)

        if (distanceFromBottom <= 240) {
            void loadMoreRecommendationRail()
        }
    }, [hasMoreRecommendationRail, loadMoreRecommendationRail, recommendationRailLoadingMore])

    const resolveCreateDraftPayload = useCallback(async (): Promise<CreateOrderDraftPayload> => {
        if (selectedDeliveryPoint?.deliveryCalculation) {
            return {
                mode: "pickup",
                provider: getOrderDraftProvider(selectedDeliveryPoint.provider),
                country_code: selectedDeliveryPoint.countryCode ?? selectedDeliveryCountry ?? "RU",
                name: selectedDeliveryPoint.name,
                full_address: buildPickupPointAddress(
                    selectedDeliveryPoint.address_full,
                    selectedDeliveryPoint.address,
                ),
                details: selectedDeliveryPoint.work_time || null,
                city: selectedDeliveryPoint.city,
                postal_code: selectedDeliveryPoint.postalCode,
                latitude: selectedDeliveryPoint.latitude,
                longitude: selectedDeliveryPoint.longitude,
                provider_reference: selectedDeliveryPoint.code,
                ...(selectedDeliveryPoint.provider === "yandex"
                    ? {
                          delivery_calculation: buildOrderDraftCalculationPayload(
                              selectedDeliveryPoint.deliveryCalculation,
                          ),
                      }
                    : {}),
            }
        }

        if (DOOR_DELIVERY_ENABLED && selectedDeliveryAddress?.deliveryCalculation) {
            return {
                mode: "door",
                provider: getOrderDraftProvider(selectedDeliveryAddress.provider),
                country_code: selectedDeliveryAddress.countryCode ?? selectedDeliveryCountry ?? "RU",
                name: selectedDeliveryAddress.address,
                full_address: selectedDeliveryAddress.address,
                details: selectedDeliveryAddress.subtitle || null,
                city: selectedDeliveryAddress.city,
                postal_code: selectedDeliveryAddress.postalCode,
                latitude: selectedDeliveryAddress.latitude,
                longitude: selectedDeliveryAddress.longitude,
                provider_reference: null,
            }
        }

        return {}
    }, [selectedDeliveryAddress, selectedDeliveryCountry, selectedDeliveryPoint])

    const handleSaveDraft = useCallback(async () => {
        if (isSavingDraft) {
            return
        }

        setIsSavingDraft(true)

        try {
            const payload = await resolveCreateDraftPayload()
            const createdDraft = await createOrderDraft({
                ...payload,
                draft_name: formatSavedCartDraftName(new Date()),
            })

            setOrderDraftSnapshot(createdDraft)
            clearBasketSnapshot()
            Alert.alert(t("cart.saveDraftSuccessTitle"), t("cart.saveDraftSuccessMessage"))
        } catch (saveError) {
            Alert.alert(
                saveError instanceof ApiError && saveError.message
                    ? saveError.message
                    : t("cart.saveDraftFailed"),
            )
        } finally {
            setIsSavingDraft(false)
        }
    }, [isSavingDraft, resolveCreateDraftPayload, t])

    const isEnteredPromoCodeApplicable = hasAppliedOrderPromo(benefitCheck, appliedPromoCode)

    const handleOpenCheckout = useCallback(async () => {
        if (!basket?.items.length || isOpeningCheckout || pricingBlocked || updating) {
            return
        }
        if (appliedPromoCode && !isEnteredPromoCodeApplicable) {
            Alert.alert(t("cart.promoCodeUnavailable"), t("cart.promoCodeUnavailableMessage"))
            return
        }
        setIsOpeningCheckout(true)

        try {
            const checkoutParams = isEnteredPromoCodeApplicable && appliedPromoCode ? { code: appliedPromoCode } : {}

            if (basketDraftEditingId !== null) {
                const nextDraft = await updateOrderDraft(basketDraftEditingId, { sync_basket_items: true })
                await clear()
                setOrderDraftSnapshot(nextDraft)
                router.push({
                    pathname: ROUTES.checkout,
                    params: {
                        draftId: String(nextDraft.id),
                        ...checkoutParams,
                    },
                })
                return
            }

            setOrderDraftSnapshot(null)
            router.push({
                pathname: ROUTES.checkout,
                params: checkoutParams,
            })
        } catch (checkoutError) {
            Alert.alert(
                checkoutError instanceof Error && checkoutError.message
                    ? checkoutError.message
                    : t("cart.checkoutFailed"),
            )
        } finally {
            setIsOpeningCheckout(false)
        }
    }, [appliedPromoCode, basket?.items.length, basketDraftEditingId, clear, isEnteredPromoCodeApplicable, isOpeningCheckout, pricingBlocked, t, updating])

    const subtotalLabel = basket ? formatProductPrice(basket.total_amount) : null
    const deliveryAmount = Number(basket?.delivery_total ?? 0)
    const deliveryLabel = basket && deliveryAmount > 0 ? formatProductPrice(basket.delivery_total) : null
    const discountAmount = Number(benefitCheck?.stacked_discount_amount ?? 0)
    const hasAppliedDiscount = discountAmount > 0
    const originalGrandTotalAmount = basket ? Number(basket.grand_total) : null
    const originalGrandTotalLabel = originalGrandTotalAmount !== null ? formatProductPrice(originalGrandTotalAmount) : null
    const grandTotalAmount = basket && !pricingBlocked
        ? (
            benefitCheck
                ? (benefitCheck.cash_total != null ? Number(benefitCheck.cash_total) : Number(benefitCheck.total_after_discounts) + deliveryAmount)
                : Number(basket.grand_total)
        )
        : null
    const grandTotalLabel = grandTotalAmount !== null ? formatProductPrice(grandTotalAmount) : null
    const handleApplyPromoCode = useCallback(async () => {
        if (!isAuthenticated || !normalizedPromoCode || !basket || isCheckingPromoCode || hasAttachedPromoCode) {
            return
        }

        setIsCheckingPromoCode(true)
        try {
            if (!await confirmPromoBinding(t("cart.applyPromoCode"),
                t("cart.confirmPartnerOrder").replace("{code}", normalizedPromoCode), t("common.cancel"))) return
            const { referrer_promo_code } = await bindMyReferrerCode(normalizedPromoCode)
            setReferralProfile(current => current ? { ...current, referrer_promo_code } : current)
            setPromoCode("")
            setAppliedPromoCode(null)
            if (milestones) milestones.bindingChanged()
            else await reloadReferralProfile()
        } catch (error) {
            Alert.alert(t("cart.promoCodeUnavailable"), getBasketErrorMessage(error, null, t))
        } finally {
            setIsCheckingPromoCode(false)
        }
    }, [basket, hasAttachedPromoCode, isAuthenticated, isCheckingPromoCode, milestones, normalizedPromoCode, reloadReferralProfile, setReferralProfile, t])
    const handlePromoCodeChange = useCallback((value: string) => {
        setPromoCode(value)
        if (appliedPromoCode && value.trim() !== appliedPromoCode) {
            setAppliedPromoCode(null)
        }
    }, [appliedPromoCode])
    const handleClearPromoCode = useCallback(() => {
        setPromoCode("")
        setAppliedPromoCode(null)
    }, [])
    const checkoutCtaLabel = grandTotalLabel
        ? `${t("cart.checkoutCta")} ${grandTotalLabel}`
        : t("cart.checkoutCta")
    const footerCtaLabel = isCheckingPromoCode
        ? t("cart.promoCodeChecking")
        : hasUnappliedPromoCode
            ? t("cart.applyPromoCode")
            : checkoutCtaLabel
    const isFooterCtaDisabled = isOpeningCheckout || isCheckingPromoCode || pricingBlocked || updating

    const cartChromeTemplate = useMemo(() => {
        if (!isReady || !basket?.items.length) {
            return null
        }

        return {
            footer: "nav+customAction" as const,
            slots: {
                footer: (
                    <View style={cartScreenStyles.footerActionStack}>
                        <View style={cartScreenStyles.footerTotalsList}>
                            {pricingBlocked ? (
                                <Text accessibilityLiveRegion="polite" style={cartScreenStyles.totalLabel}>
                                    {t(pricingError ? "cart.pricingUnavailable" : "cart.pricingUpdating")}
                                </Text>
                            ) : <>
                            {subtotalLabel ? (
                                <View style={cartScreenStyles.totalRow}>
                                    <Text style={cartScreenStyles.totalLabel}>{t("checkout.basketSubtotalLabel")}</Text>
                                    <Text style={cartScreenStyles.totalValue}>{subtotalLabel}</Text>
                                </View>
                            ) : null}
                            {deliveryLabel ? (
                                <View style={cartScreenStyles.totalRow}>
                                    <Text style={cartScreenStyles.totalLabel}>{t("checkout.deliveryCostLabel")}</Text>
                                    <Text style={cartScreenStyles.totalValue}>{deliveryLabel}</Text>
                                </View>
                            ) : null}
                            {benefitCheck?.stacked_discount_options.filter(option => Number(option.applied_discount_amount) > 0).map((option, idx) => (
                                <View key={idx} style={cartScreenStyles.totalRow}>
                                    <Text style={[cartScreenStyles.totalLabel, { flex: 1 }]}>{formatAppliedDiscount(option, t, benefitCheck.balance_redemption_mode)}</Text>
                                    <Text style={cartScreenStyles.totalValue}>−{formatProductPrice(option.applied_discount_amount)}</Text>
                                </View>
                            ))}
                            {grandTotalLabel ? (
                                <View style={[cartScreenStyles.totalRow, cartScreenStyles.totalRowGrandTotal]}>
                                    <Text style={cartScreenStyles.totalLabelStrong}>{t("checkout.grandTotalLabel")}</Text>
                                    {hasAppliedDiscount && originalGrandTotalLabel ? (
                                        <View style={cartScreenStyles.discountedTotalStack}>
                                            <Text style={cartScreenStyles.totalValueOriginal}>{originalGrandTotalLabel}</Text>
                                            <Text style={cartScreenStyles.totalValueDiscountedStrong}>{grandTotalLabel}</Text>
                                        </View>
                                    ) : (
                                        <Text style={cartScreenStyles.totalValueStrong}>{grandTotalLabel}</Text>
                                    )}
                                </View>
                            ) : null}
                            </>}
                        </View>

                        <Pressable
                            accessibilityLabel={footerCtaLabel}
                            accessibilityRole="button"
                            disabled={isFooterCtaDisabled}
                            onPress={() => {
                                if (hasUnappliedPromoCode) {
                                    handleApplyPromoCode()
                                    return
                                }

                                void handleOpenCheckout()
                            }}
                            style={({ pressed }) => [
                                stickyFooterStyles.actionButton,
                                isFooterCtaDisabled && stickyFooterStyles.actionButtonDisabled,
                                pressed && !isFooterCtaDisabled && stickyFooterStyles.actionButtonPressed,
                            ]}
                        >
                            <Text style={stickyFooterStyles.actionButtonText}>{footerCtaLabel}</Text>
                        </Pressable>
                    </View>
                ),
                headerLeft: isAuthenticated ? (
                    <Pressable
                        accessibilityLabel={t("cart.saveDraftCta")}
                        accessibilityRole="button"
                        disabled={isSavingDraft}
                        onPress={() => {
                            void handleSaveDraft()
                        }}
                        style={({ pressed }) => [
                            cartScreenStyles.headerSaveButton,
                            isSavingDraft && cartScreenStyles.headerSaveButtonDisabled,
                            pressed && cartScreenStyles.headerSaveButtonPressed,
                        ]}
                    >
                        <Svg width={22} height={22} viewBox="0 0 24 24" fill="none">
                            <Path
                                d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"
                                stroke={palette.primary}
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                            />
                            <Path
                                d="M17 21 17 13 7 13 7 21"
                                stroke={palette.primary}
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                            />
                            <Path
                                d="M7 3 7 8 15 8"
                                stroke={palette.primary}
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                            />
                        </Svg>
                    </Pressable>
                ) : null,
            },
        }
    }, [
        basket?.items.length,
        benefitCheck,
        cartScreenStyles,
        deliveryLabel,
        footerCtaLabel,
        grandTotalLabel,
        hasAppliedDiscount,
        handleApplyPromoCode,
        palette.primary,
        stickyFooterStyles,
        handleOpenCheckout,
        handleSaveDraft,
        hasUnappliedPromoCode,
        isFooterCtaDisabled,
        isAuthenticated,
        isSavingDraft,
        isReady,
        originalGrandTotalLabel,
        subtotalLabel,
        pricingError,
        pricingBlocked,
        t,
    ])
    useApplyScreenTemplate("feed", cartChromeTemplate)

    const renderStateScreen = (content: ReactNode) => (
        <View style={cartScreenStyles.container}>
            <ScrollView
                contentContainerStyle={cartScreenStyles.stateScrollContent}
                showsVerticalScrollIndicator={false}
                style={cartScreenStyles.loadingContainer}
            >
                <View style={cartScreenStyles.stateCard}>{content}</View>
            </ScrollView>
        </View>
    )

    if (!isReady || (loading && !basket)) {
        return renderStateScreen(
            <View style={cartScreenStyles.stateLoadingRow}>
                <ActivityIndicator accessibilityLabel={t("common.loading")} color={palette.primary} />
                <Text style={cartScreenStyles.errorText}>{t("common.loading")}</Text>
            </View>,
        )
    }

    if (basketLoadError && !basket) {
        return renderStateScreen(
            <>
                <Text style={cartScreenStyles.errorTitle}>{t("cart.loadFailedTitle")}</Text>
                <Text style={cartScreenStyles.errorText}>{pricingError || t("cart.loadFailedMessage")}</Text>
                <Pressable
                    accessibilityLabel={t("cart.retry")}
                    accessibilityRole="button"
                    onPress={() => {
                        if (referralError) void reloadReferralProfile()
                        else if (quoteError) void reloadQuote()
                        else void reload()
                    }}
                    style={({ pressed }) => [
                        cartScreenStyles.retryButton,
                        pressed && cartScreenStyles.pressed,
                    ]}
                >
                    <Text style={cartScreenStyles.retryButtonText}>{t("cart.retry")}</Text>
                </Pressable>
            </>,
        )
    }

    if (!basket || basket.items.length === 0) {
        return (
            <View style={cartScreenStyles.container}>
                <ScrollView
                    contentContainerStyle={cartScreenStyles.emptyScrollContent}
                    showsVerticalScrollIndicator={false}
                    style={cartScreenStyles.loadingContainer}
                >
                    <View style={cartScreenStyles.emptyContent}>
                        <EmptyState
                            sticker={STICKERS.cartEmpty}
                            description={t(hasRecentOrderDrafts ? "cart.emptyDescriptionWithDrafts" : "cart.emptyDescription")}
                            variant="plain"
                        />
                        <View style={cartScreenStyles.emptyActionsRow}>
                            <Pressable
                                accessibilityLabel={t("cart.primaryCta")}
                                accessibilityRole="button"
                                onPress={() => router.push(ROUTES.discover)}
                                style={({ pressed }) => [
                                    cartScreenStyles.emptyActionLink,
                                    pressed && cartScreenStyles.pressed,
                                ]}
                            >
                                <Text style={cartScreenStyles.emptyActionText}>{t("cart.primaryCta")}</Text>
                            </Pressable>
                            {hasRecentOrderDrafts && !recentOrderDraftsLoading ? (
                                <>
                                    <Text style={cartScreenStyles.emptyActionDivider}>·</Text>
                                    <Pressable
                                        accessibilityLabel={t("cart.openDraftsCta")}
                                        accessibilityRole="button"
                                        onPress={() => router.push(ROUTES.profileDrafts)}
                                        style={({ pressed }) => [
                                            cartScreenStyles.emptyActionLink,
                                            pressed && cartScreenStyles.pressed,
                                        ]}
                                    >
                                        <Text style={cartScreenStyles.emptyActionText}>{t("cart.openDraftsCta")}</Text>
                                    </Pressable>
                                </>
                            ) : null}
                        </View>
                    </View>
                </ScrollView>
            </View>
        )
    }

    const availableItems = basket.items.filter((item) => item.is_available)
    const unavailableItems = basket.items.filter((item) => !item.is_available)
    const hasUnavailableItems = unavailableItems.length > 0

    return (
        <View style={cartScreenStyles.container}>
            <ScrollView
                contentContainerStyle={cartScreenStyles.scrollContent}
                onScroll={handleRecommendationsScroll}
                scrollEventThrottle={16}
                showsVerticalScrollIndicator={false}
            >
                <View style={cartScreenStyles.contentSurface}>
                    {pricingBlocked ? <View style={cartScreenStyles.summarySection}>
                        <Text accessibilityLiveRegion="polite" style={cartScreenStyles.errorText}>
                            {t(pricingError ? "cart.pricingUnavailable" : "cart.pricingUpdating")}
                        </Text>
                        {pricingError ? <Pressable accessibilityRole="button" accessibilityLabel={t("cart.retry")}
                            onPress={() => { if (referralError) void reloadReferralProfile(); else void reloadQuote() }}
                            style={cartScreenStyles.retryButton}>
                            <Text style={cartScreenStyles.retryButtonText}>{t("cart.retry")}</Text>
                        </Pressable> : <ActivityIndicator color={palette.primary} />}
                    </View> : null}
                    <View style={[cartScreenStyles.summarySection, cartScreenStyles.sectionTop]}>
                        {isAuthenticated ? (
                            <View style={cartScreenStyles.summaryCard}>
                                {!programLocked || hasAttachedPromoCode ? <View style={cartScreenStyles.promoInputShell}>
                                    <TextInput
                                        autoCapitalize="characters"
                                        autoCorrect={false}
                                        editable={!programLocked && !hasAttachedPromoCode}
                                        onChangeText={handlePromoCodeChange}
                                        placeholder={t("cart.promoCodePlaceholder")}
                                        style={cartScreenStyles.promoInput}
                                        value={displayedPromoCode}
                                    />
                                    {promoCode && !hasAttachedPromoCode ? (
                                        <Pressable
                                            accessibilityLabel={t("cart.clearPromoCode")}
                                            accessibilityRole="button"
                                            hitSlop={8}
                                            onPress={handleClearPromoCode}
                                            style={({ pressed }) => [
                                                cartScreenStyles.promoClearButton,
                                                pressed && cartScreenStyles.promoClearButtonPressed,
                                            ]}
                                        >
                                            <Text style={cartScreenStyles.promoClearButtonText}>×</Text>
                                        </Pressable>
                                    ) : null}
                                </View> : null}
                            </View>
                        ) : null}

                        <View style={cartScreenStyles.summaryFooter}>
                            <View style={cartScreenStyles.summaryStats}>
                                <View
                                    style={[
                                        cartScreenStyles.summaryStat,
                                        cartScreenStyles.summaryStatStart,
                                    ]}
                                >
                                    <Text style={cartScreenStyles.summaryStatLabel}>{t("cart.positionsLabel")}</Text>
                                    <Text style={cartScreenStyles.summaryStatValue}>{basket.items_count}</Text>
                                </View>

                                <View
                                    style={[
                                        cartScreenStyles.summaryStat,
                                        cartScreenStyles.summaryStatEnd,
                                    ]}
                                >
                                    <Text style={cartScreenStyles.summaryStatLabel}>{t("cart.totalAmountLabel")}</Text>
                                    {hasAppliedDiscount && originalGrandTotalLabel ? (
                                        <View style={cartScreenStyles.discountedTotalStack}>
                                            <Text style={cartScreenStyles.summaryStatValueOriginal}>
                                                {originalGrandTotalLabel}
                                            </Text>
                                            <Text style={cartScreenStyles.summaryStatValueDiscounted}>
                                                {grandTotalLabel}
                                            </Text>
                                        </View>
                                    ) : (
                                        <Text
                                            style={[
                                                cartScreenStyles.summaryStatValue,
                                                cartScreenStyles.summaryStatValuePrice,
                                            ]}
                                        >
                                            {grandTotalLabel ?? "—"}
                                        </Text>
                                    )}
                                </View>
                            </View>

                            {basket.has_unavailable_items ? (
                                <Text style={cartScreenStyles.summaryWarning}>{t("cart.unavailableNotice")}</Text>
                            ) : null}
                        </View>
                    </View>

                    {availableItems.length ? (
                        <View style={cartScreenStyles.itemsSection}>
                            <View
                                style={[
                                    cartScreenStyles.itemsSectionCard,
                                    !hasUnavailableItems && cartScreenStyles.sectionBottom,
                                ]}
                            >
                                <View style={cartScreenStyles.itemsSectionHeader}>
                                    <Text style={cartScreenStyles.itemsSectionTitle}>
                                        {t("cart.availableItemsTitle")}
                                    </Text>
                                </View>
                                <View style={cartScreenStyles.itemsList}>
                                    {availableItems.map((item) => (
                                        <CartBasketItem
                                            key={item.id}
                                            item={getQuotedItemPrice(item, pricingBlocked ? null : benefitCheck)}
                                            onConfirmRemove={handleConfirmRemoveItem}
                                            onDecrease={(nextItem) => {
                                                void handleQuantityDecrease(nextItem)
                                            }}
                                            onIncrease={(nextItem) => {
                                                void handleQuantityIncrease(nextItem)
                                            }}
                                            onOpenProduct={handleOpenProduct}
                                            swipeableRef={(instance) => {
                                                swipeableRefs.current[item.id] = instance
                                            }}
                                            updating={updating}
                                        />
                                    ))}
                                </View>
                            </View>
                        </View>
                    ) : null}

                    {unavailableItems.length ? (
                        <View style={cartScreenStyles.itemsSection}>
                            <View
                                style={[
                                    cartScreenStyles.itemsSectionCard,
                                    cartScreenStyles.itemsSectionCardUnavailable,
                                    cartScreenStyles.sectionBottom,
                                ]}
                            >
                                <View style={cartScreenStyles.itemsSectionHeader}>
                                    <Text style={cartScreenStyles.itemsSectionTitle}>
                                        {t("cart.unavailableItemsTitle")}
                                    </Text>
                                    <Text style={cartScreenStyles.itemsSectionDescription}>
                                        {t("cart.unavailableItemsDescription")}
                                    </Text>
                                </View>
                                <View style={cartScreenStyles.itemsList}>
                                    {unavailableItems.map((item) => (
                                        <CartBasketItem
                                            key={item.id}
                                            item={getQuotedItemPrice(item, pricingBlocked ? null : benefitCheck)}
                                            onConfirmRemove={handleConfirmRemoveItem}
                                            onDecrease={(nextItem) => {
                                                void handleQuantityDecrease(nextItem)
                                            }}
                                            onIncrease={(nextItem) => {
                                                void handleQuantityIncrease(nextItem)
                                            }}
                                            onOpenProduct={handleOpenProduct}
                                            swipeableRef={(instance) => {
                                                swipeableRefs.current[item.id] = instance
                                            }}
                                            updating={updating}
                                        />
                                    ))}
                                </View>
                            </View>
                        </View>
                    ) : null}

                    {recommendationRailProducts.length ? (
                        <View style={cartScreenStyles.recommendationsSection}>
                            <ContentRail
                                title={t("recommendations.title")}
                                description={t("recommendations.productDescription")}
                                layout="grid"
                                gridVariant="discover"
                                mergeHeaderWithFirstRow
                                loadingMore={recommendationRailLoadingMore}
                                products={recommendationRailProducts}
                            />
                        </View>
                    ) : null}
                </View>
            </ScrollView>
        </View>
    )
}
