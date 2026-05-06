import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react"
import {
    ActivityIndicator,
    Alert,
    type NativeScrollEvent,
    type NativeSyntheticEvent,
    Pressable,
    ScrollView,
    Text,
    TextInput,
    View,
} from "react-native"
import { router, useLocalSearchParams } from "expo-router"
import Swipeable from "react-native-gesture-handler/Swipeable"
import { Path, Svg } from "react-native-svg"

import { ContentRail } from "@/components/content/content-rail"
import { formatProductPrice } from "@/components/content/product-content"
import { EmptyState } from "@/components/content/empty-state"
import { stickyFooterStyles } from "@/components/footer/sticky-footer.styles"
import { useApplyScreenTemplate } from "@/components/templates/screen-template.hooks"
import { getProductRoute, ROUTES } from "@/constants/routes"
import { STICKERS } from "@/constants/stickers"
import { useBasket } from "@/hooks/basket/use-basket"
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
import { useRecommendations } from "@/hooks/recommendations/use-recommendations"
import { useAsyncData } from "@/hooks/shared/use-async-data"
import { useLanguage } from "@/providers/language-provider"
import { CartBasketItem } from "@/screens/cart/cart-basket-item"
import { cartScreenStyles } from "@/screens/cart/cart-screen.styles"
import {
    buildOrderDraftCalculationPayload,
    buildPickupPointAddress,
    formatSavedCartDraftName,
    getBasketErrorMessage,
    getOrderDraftProvider,
} from "@/screens/cart/cart-screen.utils"
import { ApiError } from "@/services/api/client"
import { checkMyBenefits } from "@/services/api/benefits"
import { createOrderDraft, updateOrderDraft } from "@/services/api/order-drafts"
import type { CreateOrderDraftPayload } from "@/services/api/order-drafts.types"
import { colors } from "@/theme/colors"
import type { BasketItemRead } from "@/types/basket"

export default function CartScreen() {
    const params = useLocalSearchParams<{ draftId?: string | string[] }>()
    const { t } = useLanguage()
    const { basket, error: basketLoadError, loading, reload } = useBasket()
    const { clear, error: basketActionError, removeItem, updateItemQuantity, updating } = useBasketMutations()
    const basketDraftEditingId = useBasketDraftEditingId()
    const selectedDeliveryAddress = useSelectedDeliveryAddress()
    const selectedDeliveryPoint = useSelectedDeliveryPoint()
    const selectedDeliveryCountry = useSelectedDeliveryCountry()
    const [promoCode, setPromoCode] = useState("")
    const [isSavingDraft, setIsSavingDraft] = useState(false)
    const [isOpeningCheckout, setIsOpeningCheckout] = useState(false)
    const swipeableRefs = useRef<Record<number, Swipeable | null>>({})
    const routeDraftIdParam = Array.isArray(params.draftId) ? params.draftId[0] : params.draftId
    const { orderDrafts: recentOrderDrafts, loading: recentOrderDraftsLoading } = useRecentOrderDrafts(1)
    const hasRecentOrderDrafts = recentOrderDrafts.length > 0
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
    const normalizedPromoCode = useMemo(() => {
        const trimmedCode = promoCode.trim()
        return trimmedCode ? trimmedCode : null
    }, [promoCode])
    const { data: benefitCheck, error: benefitCheckError, loading: benefitCheckLoading } = useAsyncData({
        debounceMs: 300,
        deps: [
            basket?.total_amount ?? null,
            basket?.currency ?? null,
            basket?.items.length ?? 0,
            normalizedPromoCode,
        ],
        enabled: Boolean(basket?.items.length),
        fetcher: async () => {
            if (!basket) {
                return null
            }

            return checkMyBenefits({
                code: normalizedPromoCode,
                currency: basket.currency,
                subtotal: basket.total_amount,
            })
        },
        initialData: null,
    })

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
        if (!hasMoreRecommendations || recommendationsLoadingMore) {
            return
        }

        const distanceFromBottom =
            event.nativeEvent.contentSize.height -
            (event.nativeEvent.contentOffset.y + event.nativeEvent.layoutMeasurement.height)

        if (distanceFromBottom <= 240) {
            void loadMoreRecommendations()
        }
    }, [hasMoreRecommendations, loadMoreRecommendations, recommendationsLoadingMore])

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
                delivery_calculation: buildOrderDraftCalculationPayload(selectedDeliveryPoint.deliveryCalculation),
            }
        }

        if (selectedDeliveryAddress?.deliveryCalculation) {
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
                delivery_calculation: buildOrderDraftCalculationPayload(selectedDeliveryAddress.deliveryCalculation),
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

    const handleOpenCheckout = useCallback(async () => {
        if (!basket?.items.length || isOpeningCheckout) {
            return
        }

        setIsOpeningCheckout(true)

        try {
            const checkoutParams = normalizedPromoCode ? { code: normalizedPromoCode } : {}

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
    }, [basket?.items.length, basketDraftEditingId, clear, isOpeningCheckout, normalizedPromoCode, t])

    const subtotalLabel = basket ? formatProductPrice(basket.total_amount) : null
    const deliveryAmount = Number(basket?.delivery_total ?? 0)
    const deliveryLabel = basket && deliveryAmount > 0 ? formatProductPrice(basket.delivery_total) : null
    const discountAmount = Number(benefitCheck?.stacked_discount_amount ?? 0)
    const discountLabel = discountAmount > 0 ? `-${formatProductPrice(discountAmount)}` : null
    const grandTotalAmount = basket
        ? (
            benefitCheck
                ? Number(benefitCheck.total_after_deposit) + deliveryAmount
                : Number(basket.grand_total)
        )
        : null
    const grandTotalLabel = grandTotalAmount !== null ? formatProductPrice(grandTotalAmount) : null
    const promoCodeStatusLabel = normalizedPromoCode
        ? benefitCheckLoading
            ? t("cart.promoCodeChecking")
            : benefitCheck?.unresolved_code_reason
                ? t("cart.promoCodeNotFound")
                : benefitCheck?.entered_code_matches.some((option) => option.is_applicable)
                    ? t("cart.promoCodeApplied")
                    : benefitCheck?.entered_code_matches.length
                        ? t("cart.promoCodeUnavailable")
                        : null
        : null
    const promoCodeStatusIsError = Boolean(
        normalizedPromoCode &&
        !benefitCheckLoading &&
        (
            benefitCheck?.unresolved_code_reason ||
            (
                benefitCheck?.entered_code_matches.length &&
                !benefitCheck.entered_code_matches.some((option) => option.is_applicable)
            )
        ),
    )
    const checkoutCtaLabel = grandTotalLabel
        ? `${t("cart.checkoutCta")} ${grandTotalLabel}`
        : t("cart.checkoutCta")

    const cartChromeTemplate = useMemo(() => {
        if (!basket?.items.length) {
            return null
        }

        return {
            footer: "nav+customAction" as const,
            slots: {
                footer: (
                    <View style={cartScreenStyles.footerActionStack}>
                        <View style={cartScreenStyles.footerTotalsList}>
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
                            {discountLabel ? (
                                <View style={cartScreenStyles.totalRow}>
                                    <Text style={cartScreenStyles.totalLabel}>{t("checkout.benefitsDiscountLabel")}</Text>
                                    <Text style={[cartScreenStyles.totalValue, cartScreenStyles.totalValueDiscount]}>
                                        {discountLabel}
                                    </Text>
                                </View>
                            ) : null}
                            {grandTotalLabel ? (
                                <View style={[cartScreenStyles.totalRow, cartScreenStyles.totalRowGrandTotal]}>
                                    <Text style={cartScreenStyles.totalLabelStrong}>{t("checkout.grandTotalLabel")}</Text>
                                    <Text style={cartScreenStyles.totalValueStrong}>{grandTotalLabel}</Text>
                                </View>
                            ) : null}
                        </View>

                        <Pressable
                            accessibilityLabel={checkoutCtaLabel}
                            accessibilityRole="button"
                            disabled={isOpeningCheckout}
                            onPress={() => {
                                void handleOpenCheckout()
                            }}
                            style={({ pressed }) => [
                                stickyFooterStyles.actionButton,
                                isOpeningCheckout && stickyFooterStyles.actionButtonDisabled,
                                pressed && stickyFooterStyles.actionButtonPressed,
                            ]}
                        >
                            <Text style={stickyFooterStyles.actionButtonText}>{checkoutCtaLabel}</Text>
                        </Pressable>
                    </View>
                ),
                headerLeft: (
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
                                stroke={colors.primary}
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                            />
                            <Path
                                d="M17 21 17 13 7 13 7 21"
                                stroke={colors.primary}
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                            />
                            <Path
                                d="M7 3 7 8 15 8"
                                stroke={colors.primary}
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                            />
                        </Svg>
                    </Pressable>
                ),
            },
        }
    }, [
        basket?.items.length,
        checkoutCtaLabel,
        deliveryLabel,
        discountLabel,
        grandTotalLabel,
        handleOpenCheckout,
        handleSaveDraft,
        isOpeningCheckout,
        isSavingDraft,
        subtotalLabel,
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

    if (loading && !basket) {
        return renderStateScreen(
            <View style={cartScreenStyles.stateLoadingRow}>
                <ActivityIndicator />
            </View>,
        )
    }

    if (basketLoadError && !basket) {
        return renderStateScreen(
            <>
                <Text style={cartScreenStyles.errorTitle}>{t("cart.loadFailedTitle")}</Text>
                <Text style={cartScreenStyles.errorText}>{t("cart.loadFailedMessage")}</Text>
                <Pressable
                    accessibilityLabel={t("cart.retry")}
                    accessibilityRole="button"
                    onPress={() => {
                        void reload()
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
                            actionVariant="link"
                            sticker={STICKERS.cartEmpty}
                            description={t(hasRecentOrderDrafts ? "cart.emptyDescriptionWithDrafts" : "cart.emptyDescription")}
                            actionLabel={t("cart.primaryCta")}
                            onPressAction={() => router.push(ROUTES.discover)}
                            variant="plain"
                        />
                        {hasRecentOrderDrafts && !recentOrderDraftsLoading ? (
                            <Pressable
                                accessibilityLabel={t("cart.openDraftsCta")}
                                accessibilityRole="button"
                                onPress={() => router.push(ROUTES.profileDrafts)}
                                style={({ pressed }) => [
                                    cartScreenStyles.emptyDraftLink,
                                    pressed && cartScreenStyles.pressed,
                                ]}
                            >
                                <Text style={cartScreenStyles.emptyDraftLinkText}>{t("cart.openDraftsCta")}</Text>
                            </Pressable>
                        ) : null}
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
                    <View style={[cartScreenStyles.summarySection, cartScreenStyles.sectionTop]}>
                        <View style={cartScreenStyles.summaryCard}>
                            <TextInput
                                autoCapitalize="characters"
                                autoCorrect={false}
                                onChangeText={setPromoCode}
                                placeholder={t("cart.promoCodePlaceholder")}
                                style={cartScreenStyles.promoInput}
                                value={promoCode}
                            />
                            {promoCodeStatusLabel ? (
                                <Text
                                    style={[
                                        cartScreenStyles.promoStatusText,
                                        promoCodeStatusIsError
                                            ? cartScreenStyles.promoStatusTextError
                                            : cartScreenStyles.promoStatusTextSuccess,
                                    ]}
                                >
                                    {promoCodeStatusLabel}
                                </Text>
                            ) : benefitCheckError ? (
                                <Text style={[cartScreenStyles.promoStatusText, cartScreenStyles.promoStatusTextError]}>
                                    {benefitCheckError}
                                </Text>
                            ) : null}
                        </View>

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
                                    <Text
                                        style={[
                                            cartScreenStyles.summaryStatValue,
                                            cartScreenStyles.summaryStatValuePrice,
                                        ]}
                                    >
                                        {grandTotalLabel ?? "—"}
                                    </Text>
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
                                            item={item}
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
                                            item={item}
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

                    {recommendedProducts.length ? (
                        <View style={cartScreenStyles.recommendationsSection}>
                            <ContentRail
                                title={t("recommendations.title")}
                                description={t("recommendations.productDescription")}
                                layout="grid"
                                gridVariant="discover"
                                mergeHeaderWithFirstRow
                                loadingMore={recommendationsLoadingMore}
                                products={recommendedProducts}
                            />
                        </View>
                    ) : null}
                </View>
            </ScrollView>
        </View>
    )
}
