import { AppFormLayout } from "@/components/platform/app-form-layout"
import { AppPickerPanel } from "@/components/platform/app-picker"
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react"
import { Picker } from "@react-native-picker/picker"
import {
    ActivityIndicator,
    Alert,
    Image,
    Keyboard,
    Modal,
    type NativeScrollEvent,
    type NativeSyntheticEvent,
    Platform,
    Pressable,
    ScrollView,
    Text,
    TextInput,
    View,
} from "react-native"
import { router, useFocusEffect, useLocalSearchParams } from "expo-router"
import { useSafeAreaInsets } from "react-native-safe-area-context"

import { ContentRail } from "@/components/content/content-rail"
import { createContentStyles } from "@/components/content/content.styles"
import {
    setSelectedDeliveryAddress,
} from "@/hooks/delivery/delivery-address-selection-store"
import { clearBasketSnapshot, setBasketSnapshot } from "@/hooks/basket/basket-store"
import { useBasket } from "@/hooks/basket/use-basket"
import { useOrderBenefits } from "@/hooks/basket/use-order-benefits"
import { setBasketDraftEditingId } from "@/hooks/basket/basket-draft-editing-store"
import { useBasketMutations } from "@/hooks/basket/use-basket-mutations"
import { setSelectedDeliveryCountry } from "@/hooks/delivery/delivery-country-selection-store"
import { setSelectedDeliveryPoint } from "@/hooks/delivery/delivery-point-selection-store"
import { setOrderDraftSnapshot } from "@/hooks/order-draft/order-draft-store"
import { useOrderDraft } from "@/hooks/order-draft/use-order-draft"
import { useInfiniteProductCatalog } from "@/hooks/products/use-infinite-product-catalog"
import { useRecommendations } from "@/hooks/recommendations/use-recommendations"
import { useAsyncData } from "@/hooks/shared/use-async-data"
import { useApplyScreenTemplate } from "@/components/templates/screen-template.hooks"
import { ROUTES } from "@/constants/routes"
import { useAuth } from "@/providers/auth-provider"
import { useLanguage } from "@/providers/language-provider"
import { getBasketErrorMessage } from "@/screens/cart/cart-screen.utils"
import {
    ADD_NEW_ADDRESS_VALUE,
    NO_ADDRESS_VALUE,
    ADD_NEW_RECIPIENT_VALUE,
    NO_RECIPIENT_VALUE,
    SELF_RECIPIENT_VALUE,
} from "@/screens/checkout/checkout-screen.constants"
import { createCheckoutScreenStyles } from "@/screens/checkout/checkout-screen.styles"
import { useCheckoutRecipientSelection } from "@/screens/checkout/use-checkout-recipient-selection"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useTheme } from "@/providers/theme-provider"
import type {
    ExpandedSection,
    RecipientFormErrors,
    RecipientFormState,
} from "@/screens/checkout/checkout-screen.types"
import {
    buildAddressUpdatePayloadWithCalculation,
    basketMatchesDraft,
    buildAvailableAddresses,
    calculateDeliveryForSavedAddress,
    buildAvailableRecipients,
    buildCheckoutDraftFromBasket,
    buildDraftPayloadFromOrderDraft,
    createEmptyRecipientForm,
    formatMoney,
    recipientPickerLabel,
    formatSavedCartDraftName,
    getDraftRecipient,
    getSelfRecipient,
    getProfileRecipientUpdate,
    getDraftUpdateErrorMessage,
    getRecipientFormFromRecipient,
    getRecipientFormErrors,
    getRecipientPickerValue,
    hasRecipientErrors,
    normalizePhoneValue,
    normalizeTextInputValue,
    parseDraftId,
    resolveRecipientPickerAction,
    updateSavedRecipientOptions,
} from "@/screens/checkout/checkout-screen.utils"
import { getBasketCheckoutOptions, restoreDraftToBasket, updateBasketCheckout, updateBasketItem } from "@/services/api/basket"
import { checkMyBenefits } from "@/services/api/benefits"
import { checkGuestPhone } from "@/services/api/guest"
import { createOrderDraft, getOrderDraftOptions, updateOrderDraft } from "@/services/api/order-drafts"
import type {
    DeliveryRecipientRead,
    OrderDraftCheckoutOptionsRead,
    OrderDraftItemRead,
    OrderDraftRead,
} from "@/services/api/order-drafts.types"
import { getMyReferralProfile } from "@/services/api/users"
import { hasAppliedOrderPromo } from "@/screens/cart/order-promo"
import type { ReferralProfileResponse } from "@/services/api/users.types"
import { updateGuestBasketCheckout, updateGuestCartItemQuantity } from "@/services/guest-cart"
import { spacing } from "@/theme/spacing"
import { formatAppliedDiscount } from "@/utils/discount-display"
import { getQuotedItemPrice } from "@/utils/quoted-item-price"
import { CheckoutAddressPicker } from "@/screens/checkout/checkout-address-picker"

export default function CheckoutScreen() {
    const contentStyles = useThemeStyles(createContentStyles)
    const checkoutScreenStyles = useThemeStyles(createCheckoutScreenStyles)
    const { palette } = useTheme()
    const { isAuthenticated, isReady, updatePersonalData, user } = useAuth()
    const { t, language } = useLanguage()
    const { bottom: bottomInset, top: topInset } = useSafeAreaInsets()
    const params = useLocalSearchParams<{ code?: string | string[], draftId?: string | string[] }>()
    const draftId = parseDraftId(params.draftId)
    const routePromoCode = normalizeTextInputValue((Array.isArray(params.code) ? params.code[0] : params.code) ?? "")
    const { basket, error: basketLoadError, loading: basketLoading, reload: reloadBasket } = useBasket()
    const { error: basketError, restoreDraft, updating: isRestoringDraft } = useBasketMutations()
    const isBasketCheckout = draftId === null
    const { orderDraft: savedOrderDraft, error, loading, reload } = useOrderDraft(draftId)
    const orderDraft = useMemo(
        () => (isBasketCheckout && basket ? buildCheckoutDraftFromBasket(basket) : savedOrderDraft),
        [basket, isBasketCheckout, savedOrderDraft],
    )
    const recommendationsSurface = isBasketCheckout ? "cart" : "draft"
    const recommendationsDraftId = isBasketCheckout ? null : orderDraft?.id ?? null
    const shouldLoadRecommendations = Boolean(
        isAuthenticated && orderDraft?.items.length && (isBasketCheckout || recommendationsDraftId),
    )
    const {
        hasMore: hasMoreRecommendations,
        loadMore: loadMoreRecommendations,
        loadingMore: recommendationsLoadingMore,
        products: recommendedProducts,
    } = useRecommendations({
        surface: recommendationsSurface,
        draftId: recommendationsDraftId,
        limit: 6,
        enabled: shouldLoadRecommendations,
        deps: [orderDraft?.updated_at ?? null, orderDraft?.items.length ?? 0],
    })
    const {
        hasMore: hasMoreGuestCatalog,
        loadMore: loadMoreGuestCatalog,
        loadingMore: guestCatalogLoadingMore,
        products: guestCatalogProducts,
    } = useInfiniteProductCatalog({
        enabled: Boolean(!isAuthenticated && orderDraft?.items.length),
        pageSize: 6,
        sort: "newest",
    })
    const recommendationRailProducts = isAuthenticated ? recommendedProducts : guestCatalogProducts
    const recommendationRailLoadingMore = isAuthenticated ? recommendationsLoadingMore : guestCatalogLoadingMore
    const hasMoreRecommendationRail = isAuthenticated ? hasMoreRecommendations : hasMoreGuestCatalog
    const loadMoreRecommendationRail = isAuthenticated ? loadMoreRecommendations : loadMoreGuestCatalog
    const {
        data: checkoutOptions, error: optionsError, loading: optionsLoading,
        reload: reloadCheckoutOptions, setData: setCheckoutOptions,
    } = useAsyncData<OrderDraftCheckoutOptionsRead | null>({
        deps: [isBasketCheckout, user?.id ?? null, orderDraft?.id ?? null],
        enabled: Boolean(orderDraft?.id),
        fetcher: async () => {
            if (isBasketCheckout) {
                if (!isAuthenticated) {
                    return {
                        addresses: [],
                        recipients: [],
                    }
                }

                return getBasketCheckoutOptions()
            }

            if (!orderDraft?.id) {
                return null
            }

            return getOrderDraftOptions(orderDraft.id)
        },
        initialData: null,
        resetOnLoad: true,
    })
    const {
        data: referralProfile,
        error: referralError,
        reload: reloadReferralProfile,
    } = useAsyncData<ReferralProfileResponse | null>({
        deps: [user?.id ?? null, user?.programSelectionRequired, orderDraft?.id ?? null, isBasketCheckout],
        enabled: Boolean(orderDraft?.items.length && isAuthenticated && !user?.programSelectionRequired),
        fetcher: getMyReferralProfile,
        initialData: null,
        resetOnLoad: true,
    })
    const [openPickerSection, setOpenPickerSection] = useState<ExpandedSection>(null)
    const [isRecipientEditorOpen, setIsRecipientEditorOpen] = useState(false)
    const [profileFieldsToComplete, setProfileFieldsToComplete] = useState<RecipientFormErrors | null>(null)
    const [isCorrectingRecipient, setIsCorrectingRecipient] = useState(false)
    const [isSavingRecipient, setIsSavingRecipient] = useState(false)
    const [isSavingAddress, setIsSavingAddress] = useState(false)
    const [selectedAddressValue, setSelectedAddressValue] = useState<number | typeof ADD_NEW_ADDRESS_VALUE | null>(null)
    const [draftAddressValue, setDraftAddressValue] = useState<number | typeof NO_ADDRESS_VALUE | typeof ADD_NEW_ADDRESS_VALUE>(NO_ADDRESS_VALUE)
    const [recipientForm, setRecipientForm] = useState<RecipientFormState>(createEmptyRecipientForm())
    const [recipientFormErrors, setRecipientFormErrors] = useState<RecipientFormErrors>({})
    const [recipientSaveError, setRecipientSaveError] = useState<string | null>(null)
    const [promoCode, setPromoCode] = useState(routePromoCode ?? "")
    const [appliedPromoCode, setAppliedPromoCode] = useState<string | null>(routePromoCode ?? null)
    const [isCheckingPromoCode, setIsCheckingPromoCode] = useState(false)
    const appliedRoutePromoCodeRef = useRef<string | null>(routePromoCode ?? null)
    const focusedRecipientInputRef = useRef<TextInput | null>(null)
    const recipientEmailInputRef = useRef<TextInput>(null)
    const recipientFirstNameInputRef = useRef<TextInput>(null)
    const recipientLastNameInputRef = useRef<TextInput>(null)
    const recipientPhoneInputRef = useRef<TextInput>(null)
    const recipientEditorScrollOffsetRef = useRef(0)
    const recipientEditorScrollRef = useRef<ScrollView>(null)
    const scrollRecipientInputIntoView = useCallback((keyboardScreenY = Keyboard.metrics()?.screenY) => {
        const input = focusedRecipientInputRef.current

        if (!input || keyboardScreenY === undefined) {
            return
        }

        requestAnimationFrame(() => {
            input.measure((_x, _y, _width, height, _pageX, pageY) => {
                const overlap = pageY + height + spacing.sm - keyboardScreenY

                if (overlap <= 0) {
                    return
                }

                recipientEditorScrollRef.current?.scrollTo({
                    animated: true,
                    y: recipientEditorScrollOffsetRef.current + overlap,
                })
            })
        })
    }, [])
    const handleRecipientInputFocus = useCallback(
        (input: TextInput | null) => {
            focusedRecipientInputRef.current = input
            scrollRecipientInputIntoView()
        },
        [scrollRecipientInputIntoView],
    )

    useEffect(() => {
        if (!isRecipientEditorOpen) {
            return
        }

        recipientEditorScrollOffsetRef.current = 0
        requestAnimationFrame(() => {
            recipientEditorScrollRef.current?.scrollTo({ animated: false, y: 0 })
        })

        const subscription = Keyboard.addListener("keyboardDidShow", (event) => {
            scrollRecipientInputIntoView(event.endCoordinates.screenY)
        })

        return () => {
            subscription.remove()
        }
    }, [isRecipientEditorOpen, scrollRecipientInputIntoView])

    const normalizedPromoCode = useMemo(() => {
        const trimmedCode = promoCode.trim()
        return trimmedCode ? trimmedCode : null
    }, [promoCode])
    const attachedPromoCode = referralProfile?.promo_code ?? null
    const programLocked = !referralProfile || Boolean(user?.programSelectionRequired)
    const hasAttachedPromoCode = Boolean(attachedPromoCode)
    const displayedPromoCode = attachedPromoCode ?? promoCode
    const hasUnappliedPromoCode = Boolean(isAuthenticated && !programLocked && !hasAttachedPromoCode && normalizedPromoCode && normalizedPromoCode !== appliedPromoCode)
    const isPromoRewardReady = programLocked || !normalizedPromoCode || hasAttachedPromoCode || Boolean(appliedPromoCode)
    const activeEnteredPromoCode = !programLocked && !hasAttachedPromoCode ? appliedPromoCode : null
    const quoteSource = { use_basket: isBasketCheckout, draft_id: isBasketCheckout ? null : orderDraft?.id }
    const needsQuote = Boolean(orderDraft?.items.length && isAuthenticated && !user?.programSelectionRequired)
    const { data: benefitCheck, error: quoteError, reload: reloadQuote } = useOrderBenefits(
        [user?.id, attachedPromoCode, orderDraft?.id, orderDraft?.delivery_total, orderDraft?.currency,
            orderDraft?.items.map(item => [item.variant_id, item.quantity, item.line_total])],
        needsQuote && referralProfile !== null,
        { ...quoteSource, code: activeEnteredPromoCode, reward_mode: activeEnteredPromoCode ? "order_referral" : undefined },
    )
    const rewardMode = benefitCheck?.reward_mode
    const pricingError = needsQuote && (referralError || quoteError)
    const waitingForPricing = needsQuote && !pricingError && !benefitCheck
    const waitingForCheckout = !isReady || waitingForPricing || Boolean(orderDraft && optionsLoading && !checkoutOptions)

    useEffect(() => {
        if (!routePromoCode || appliedRoutePromoCodeRef.current === routePromoCode) {
            return
        }

        appliedRoutePromoCodeRef.current = routePromoCode
        setPromoCode(routePromoCode)
        setAppliedPromoCode(routePromoCode)
    }, [routePromoCode])

    useFocusEffect(
        useCallback(() => (
            () => {
                setOpenPickerSection(null)
                setIsRecipientEditorOpen(false)
            }
        ), []),
    )

    useFocusEffect(
        useCallback(() => {
            if (orderDraft && isAuthenticated) {
                void reloadReferralProfile({ showLoading: false })
            }
        }, [isAuthenticated, orderDraft, reloadReferralProfile]),
    )

    const recipientScope = `${isBasketCheckout ? "basket" : "draft"}:${user?.id ?? "guest"}:${orderDraft?.id ?? ""}`
    const snapshotRecipient = useMemo(() => getDraftRecipient(orderDraft), [orderDraft])
    const { recipient: savedRecipient, confirmRecipient } = useCheckoutRecipientSelection(
        recipientScope, snapshotRecipient,
    )
    const selfRecipient = useMemo(() => getSelfRecipient(user), [user])
    const currentRecipient = savedRecipient ?? selfRecipient
    const isSelfSelected = !savedRecipient && Boolean(selfRecipient)
    const deliveryCost = orderDraft?.delivery_address
        ? formatMoney(Number(orderDraft.delivery_total), orderDraft.currency)
        : null
    const basketSubtotal = orderDraft
        ? formatMoney(Number(orderDraft.basket_subtotal), orderDraft.currency)
        : null
    const grandTotal = orderDraft
        ? formatMoney(
            benefitCheck
                ? (benefitCheck.cash_total != null
                    ? Number(benefitCheck.cash_total)
                    : Number(benefitCheck.total_after_discounts) + Number(orderDraft.delivery_total))
                : Number(orderDraft.grand_total),
            orderDraft.currency,
        )
        : null
    const activeAddressId = orderDraft?.delivery_address?.id
    const hasDeliveryAddress = Boolean(orderDraft?.delivery_address)
    const hasRecipient = Boolean(currentRecipient)
    const selectedRecipientForm = useMemo(() => getRecipientFormFromRecipient(currentRecipient), [currentRecipient])
    const selectedRecipientErrors = useMemo(() => getRecipientFormErrors(selectedRecipientForm, t), [selectedRecipientForm, t])
    const needsRecipientCorrection = hasRecipient && hasRecipientErrors(selectedRecipientErrors)
    const payCtaLabel = grandTotal
        ? `${t("checkout.payCta")} ${grandTotal}`
        : t("checkout.payCta")
    const recipientCorrectionLabel = isSelfSelected ? t("checkout.completeProfile") : t("checkout.correctRecipient")
    const paymentFooterCtaLabel = !hasDeliveryAddress
        ? t("checkout.openDelivery")
        : !hasRecipient
            ? t("checkout.selectRecipient")
            : needsRecipientCorrection
                ? recipientCorrectionLabel
                : payCtaLabel
    const checkoutFooterCtaLabel = isCheckingPromoCode
        ? t("checkout.promoCodeChecking")
        : hasUnappliedPromoCode
            ? t("checkout.applyPromoCode")
            : !isPromoRewardReady
                ? t("checkout.enterPromoCode")
                : paymentFooterCtaLabel
    const isCheckoutFooterCtaDisabled =
        isCheckingPromoCode
        || isSavingRecipient
        || (!hasUnappliedPromoCode && !isPromoRewardReady)
    const [isUpdatingPositions, setIsUpdatingPositions] = useState(false)
    const isPositionsBusy = isRestoringDraft || isUpdatingPositions
    const isAddProductsBusy = isRestoringDraft
    const handleApplyPromoCode = useCallback(async () => {
        if (!isAuthenticated || !normalizedPromoCode || !orderDraft || isCheckingPromoCode || hasAttachedPromoCode) {
            return
        }

        setIsCheckingPromoCode(true)
        try {
            const nextBenefitCheck = await checkMyBenefits({
                use_basket: isBasketCheckout, draft_id: isBasketCheckout ? null : orderDraft.id,
                code: normalizedPromoCode, reward_mode: "order_referral",
            })

            const hasCodeMatch = Boolean(
                !nextBenefitCheck.unresolved_code_reason && nextBenefitCheck.entered_code_matches.length,
            )
            const isApplicable = nextBenefitCheck.entered_code_matches.some((option) => option.is_applicable)
            const hasDiscount = hasAppliedOrderPromo(nextBenefitCheck, normalizedPromoCode)

            if (!hasCodeMatch) {
                setAppliedPromoCode(null)
                Alert.alert(t("checkout.promoCodeNotFound"), nextBenefitCheck.unresolved_code_reason || t("checkout.promoCodeNotFoundMessage"))
                return
            }

            if (!isApplicable || !hasDiscount) {
                setAppliedPromoCode(null)
                Alert.alert(t("checkout.promoCodeUnavailable"), t("checkout.promoCodeUnavailableMessage"))
                return
            }

            if (referralProfile?.reward_program !== "partner") {
                Alert.alert(t("cart.applyPromoCode"), t("cart.confirmPartnerOrder"), [
                    { text: t("common.cancel"), style: "cancel" },
                    { text: t("cart.applyPromoCode"), onPress: () => setAppliedPromoCode(normalizedPromoCode) },
                ])
            } else {
                setAppliedPromoCode(normalizedPromoCode)
            }
        } catch (error) {
            setAppliedPromoCode(null)
            Alert.alert(t("checkout.promoCodeUnavailable"), getDraftUpdateErrorMessage(error, t("checkout.promoCodeUnavailableMessage")))
        } finally {
            setIsCheckingPromoCode(false)
        }
    }, [
        hasAttachedPromoCode,
        isAuthenticated,
        isCheckingPromoCode,
        isBasketCheckout,
        normalizedPromoCode,
        orderDraft,
        referralProfile?.reward_program,
        t,
    ])
    const handlePromoCodeChange = useCallback((value: string) => {
        setPromoCode(value)
        if (appliedPromoCode && value.trim() !== appliedPromoCode) {
            setAppliedPromoCode(null)
        }
    }, [appliedPromoCode])
    const openPaymentFlow = useCallback((paymentMethod: "later" | "sbp") => {
        if (!orderDraft || !hasDeliveryAddress || !hasRecipient || needsRecipientCorrection || waitingForCheckout || pricingError || optionsError) {
            return
        }

        router.push({
            pathname: ROUTES.payment,
            params: {
                paymentMethod,
                ...(isBasketCheckout ? {} : { draftId: String(orderDraft.id) }),
                ...(activeEnteredPromoCode ? { code: activeEnteredPromoCode } : {}),
                ...(rewardMode ? { rewardMode } : {}),
            },
        })
    }, [activeEnteredPromoCode, hasDeliveryAddress, hasRecipient, isBasketCheckout, needsRecipientCorrection, optionsError, orderDraft, pricingError, rewardMode, waitingForCheckout])

    const handlePressPay = useCallback(() => {
        Alert.alert(t("checkout.paymentMethodTitle"), undefined, [
            {
                text: t("checkout.paymentMethodCancel"),
                style: "cancel",
            },
            {
                text: t("payment.methodLaterTitle"),
                onPress: () => {
                    openPaymentFlow("later")
                },
            },
            {
                text: t("payment.methodSbpTitle"),
                onPress: () => {
                    openPaymentFlow("sbp")
                },
            },
        ])
    }, [openPaymentFlow, t])
    const handleOpenPicker = useCallback((section: Exclude<ExpandedSection, null>) => {
        Keyboard.dismiss()

        if (section === "address") {
            setDraftAddressValue(selectedAddressValue === ADD_NEW_ADDRESS_VALUE ? NO_ADDRESS_VALUE : selectedAddressValue ?? activeAddressId ?? NO_ADDRESS_VALUE)
        }
        setOpenPickerSection(section)
    }, [activeAddressId, selectedAddressValue])

    const handleOpenRecipientEditor = useCallback((
        form = createEmptyRecipientForm(),
        profileFields: RecipientFormErrors | null = null,
        errors: RecipientFormErrors = {},
    ) => {
        Keyboard.dismiss()
        focusedRecipientInputRef.current = null
        setOpenPickerSection(null)
        setProfileFieldsToComplete(profileFields)
        setIsCorrectingRecipient(hasRecipientErrors(errors))
        setRecipientForm(form)
        setRecipientFormErrors(errors)
        setRecipientSaveError(null)
        setIsRecipientEditorOpen(true)
    }, [])

    const handleCheckoutFooterCtaPress = useCallback(() => {
        if (hasUnappliedPromoCode) {
            void handleApplyPromoCode()
            return
        }

        if (!orderDraft || !isPromoRewardReady || isSavingRecipient) return
        if (!hasDeliveryAddress || !hasRecipient) {
            handleOpenPicker(hasDeliveryAddress ? "recipient" : "address")
            return
        }

        if (needsRecipientCorrection) {
            handleOpenRecipientEditor(selectedRecipientForm, isSelfSelected ? selectedRecipientErrors : null, selectedRecipientErrors)
            return
        }

        handlePressPay()
    }, [
        handleApplyPromoCode, handleOpenPicker, handleOpenRecipientEditor, handlePressPay,
        hasDeliveryAddress, hasRecipient, hasUnappliedPromoCode, isPromoRewardReady,
        isSavingRecipient, isSelfSelected, needsRecipientCorrection, orderDraft,
        selectedRecipientErrors, selectedRecipientForm,
    ])

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

    const checkoutChromeTemplate = useMemo(() => {
        if (!orderDraft || waitingForCheckout || pricingError || optionsError) {
            return null
        }

        return {
            footer: "nav+customAction" as const,
            slots: {
                footer: (
                    <View style={checkoutScreenStyles.footerActionStack}>
                        <View style={checkoutScreenStyles.footerTotalsList}>
                            {basketSubtotal ? (
                                <View style={checkoutScreenStyles.totalRow}>
                                    <Text style={checkoutScreenStyles.totalLabel}>{t("checkout.basketSubtotalLabel")}</Text>
                                    <Text style={checkoutScreenStyles.totalValue}>{basketSubtotal}</Text>
                                </View>
                            ) : null}
                            {deliveryCost ? (
                                <View style={checkoutScreenStyles.totalRow}>
                                    <Text style={checkoutScreenStyles.totalLabel}>{t("checkout.deliveryCostLabel")}</Text>
                                    <Text style={checkoutScreenStyles.totalValue}>{deliveryCost}</Text>
                                </View>
                            ) : null}
                            {benefitCheck?.stacked_discount_options.filter(option => Number(option.applied_discount_amount) > 0).map((option) => (
                                <View
                                    key={`${option.source_kind}-${option.source_record_id ?? option.code ?? option.sequence}`}
                                    style={checkoutScreenStyles.totalRow}
                                >
                                    <Text style={[checkoutScreenStyles.totalLabel, { flex: 1 }]}>{formatAppliedDiscount(option, t, benefitCheck.balance_redemption_mode)}</Text>
                                    <Text style={[checkoutScreenStyles.totalValue, checkoutScreenStyles.totalValueDiscount]}>
                                        {option.applied_discount_amount
                                            ? `−${formatMoney(Number(option.applied_discount_amount), option.currency ?? benefitCheck.currency)}`
                                            : null}
                                    </Text>
                                </View>
                            ))}
                            {grandTotal ? (
                                <View style={[checkoutScreenStyles.totalRow, checkoutScreenStyles.totalRowGrandTotal]}>
                                    <Text style={checkoutScreenStyles.totalLabelStrong}>{t("checkout.grandTotalLabel")}</Text>
                                    <Text style={checkoutScreenStyles.totalValueStrong}>{grandTotal}</Text>
                                </View>
                            ) : null}
                        </View>

                        <Pressable
                            accessibilityLabel={checkoutFooterCtaLabel}
                            accessibilityRole="button"
                            disabled={isCheckoutFooterCtaDisabled}
                            onPress={handleCheckoutFooterCtaPress}
                            style={({ pressed }) => [
                                checkoutScreenStyles.footerCtaButton,
                                isCheckoutFooterCtaDisabled && checkoutScreenStyles.footerCtaButtonDisabled,
                                pressed && !isCheckoutFooterCtaDisabled && checkoutScreenStyles.footerCtaButtonPressed,
                            ]}
                        >
                            <Text
                                style={[
                                    checkoutScreenStyles.footerCtaButtonText,
                                    isCheckoutFooterCtaDisabled && checkoutScreenStyles.footerCtaButtonTextDisabled,
                                ]}
                            >
                                {checkoutFooterCtaLabel}
                            </Text>
                        </Pressable>
                    </View>
                ),
            },
        }
    }, [
        basketSubtotal,
        benefitCheck,
        checkoutScreenStyles,
        checkoutFooterCtaLabel,
        deliveryCost,
        grandTotal,
        handleCheckoutFooterCtaPress,
        isCheckoutFooterCtaDisabled,
        orderDraft,
        optionsError,
        pricingError,
        t,
        waitingForCheckout,
    ])
    useApplyScreenTemplate("feed", checkoutChromeTemplate)
    const availableRecipients = !isAuthenticated && savedRecipient
        ? [savedRecipient]
        : buildAvailableRecipients(savedRecipient, checkoutOptions)
    const recipientPrimaryText = isSelfSelected
        ? t("checkout.recipientForMyself")
        : currentRecipient ? recipientPickerLabel(currentRecipient, availableRecipients) : t("checkout.selectRecipient")
    const recipientEditorTitle = profileFieldsToComplete
        ? t("checkout.completeProfile")
        : isCorrectingRecipient
            ? t("checkout.correctRecipient")
            : t("checkout.recipientAddNew")
    const recipientPickerValue = getRecipientPickerValue(savedRecipient, Boolean(selfRecipient))
    const availableAddresses = useMemo(() => {
        return orderDraft ? buildAvailableAddresses(orderDraft, checkoutOptions) : []
    }, [checkoutOptions, orderDraft])
    const showRecipientField = (field: keyof RecipientFormState) =>
        profileFieldsToComplete === null || Boolean(profileFieldsToComplete[field])
    const recipientSaveLabel = t(profileFieldsToComplete ? "checkout.saveToProfile" : "checkout.recipientCreateAction")

    useEffect(() => {
        if (!orderDraft) {
            return
        }

        if (!orderDraft.delivery_address) {
            setSelectedAddressValue(ADD_NEW_ADDRESS_VALUE)
            setDraftAddressValue(NO_ADDRESS_VALUE)
            return
        }

        setSelectedAddressValue(orderDraft.delivery_address.id)
        setDraftAddressValue(orderDraft.delivery_address.id)
    }, [orderDraft])

    const renderStateScreen = (content: ReactNode) => (
        <View style={checkoutScreenStyles.container}>
            <ScrollView
                contentContainerStyle={checkoutScreenStyles.content}
                keyboardShouldPersistTaps="handled"
                style={checkoutScreenStyles.scrollView}
            >
                <View
                    style={[
                        checkoutScreenStyles.stateCard,
                        checkoutScreenStyles.stateCardTop,
                        checkoutScreenStyles.stateCardBottom,
                    ]}
                >
                    {content}
                </View>
            </ScrollView>
        </View>
    )

    const checkoutLoading = isBasketCheckout ? basketLoading : loading
    const checkoutError = isBasketCheckout ? basketLoadError : error

    if ((checkoutLoading && !orderDraft) || waitingForCheckout) {
        return renderStateScreen(
            <View style={checkoutScreenStyles.stateLoadingRow}>
                <ActivityIndicator accessibilityLabel={t("common.loading")} color={palette.primary} />
                <Text style={checkoutScreenStyles.loadingText}>{t("common.loading")}</Text>
            </View>,
        )
    }

    if ((checkoutError && !orderDraft) || pricingError || optionsError) {
        return renderStateScreen(
            <>
                <Text style={checkoutScreenStyles.sectionTitle}>{t("checkout.loadFailedTitle")}</Text>
                <Text style={checkoutScreenStyles.stateText}>{pricingError || optionsError || t("checkout.loadFailedMessage")}</Text>
                <View style={[checkoutScreenStyles.actionRow, checkoutScreenStyles.actionRowSingle]}>
                    <Pressable
                        accessibilityLabel={t("checkout.retry")}
                        accessibilityRole="button"
                        onPress={() => {
                            if (referralError) void reloadReferralProfile()
                            else if (quoteError) void reloadQuote()
                            else if (optionsError) void reloadCheckoutOptions()
                            else if (isBasketCheckout) void reloadBasket()
                            else void reload()
                        }}
                        style={({ pressed }) => [
                            checkoutScreenStyles.secondaryButton,
                            checkoutScreenStyles.secondaryButtonFullWidth,
                            pressed && checkoutScreenStyles.secondaryButtonPressed,
                        ]}
                    >
                        <Text style={checkoutScreenStyles.secondaryButtonText}>{t("checkout.retry")}</Text>
                    </Pressable>
                    <Pressable
                        accessibilityLabel={t("checkout.openBasket")}
                        accessibilityRole="button"
                        onPress={() => {
                            router.push(ROUTES.basket)
                        }}
                        style={({ pressed }) => [
                            checkoutScreenStyles.secondaryButton,
                            checkoutScreenStyles.secondaryButtonFullWidth,
                            pressed && checkoutScreenStyles.secondaryButtonPressed,
                        ]}
                    >
                        <Text style={checkoutScreenStyles.secondaryButtonText}>{t("checkout.openBasket")}</Text>
                    </Pressable>
                </View>
            </>,
        )
    }

    if (!orderDraft) {
        return renderStateScreen(
            <>
                <Text style={checkoutScreenStyles.sectionTitle}>{t("checkout.noDraftTitle")}</Text>
                <Text style={checkoutScreenStyles.stateText}>{t("checkout.noDraftMessage")}</Text>
                <Pressable
                    accessibilityLabel={t("checkout.openBasket")}
                    accessibilityRole="button"
                    onPress={() => {
                        router.push(ROUTES.basket)
                    }}
                    style={({ pressed }) => [
                        checkoutScreenStyles.secondaryButton,
                        checkoutScreenStyles.secondaryButtonFullWidth,
                        pressed && checkoutScreenStyles.secondaryButtonPressed,
                    ]}
                >
                    <Text style={checkoutScreenStyles.secondaryButtonText}>{t("checkout.openBasket")}</Text>
                </Pressable>
            </>,
        )
    }

    const closeCheckoutPicker = () => {
        setOpenPickerSection(null)
    }

    const handleCloseRecipientEditor = () => {
        Keyboard.dismiss()
        focusedRecipientInputRef.current = null
        setRecipientFormErrors({})
        setRecipientSaveError(null)
        setIsRecipientEditorOpen(false)
    }

    const applyUpdatedDraft = async (nextDraft: OrderDraftRead) => {
        setOrderDraftSnapshot(nextDraft)
        await reloadCheckoutOptions({ showLoading: false })
    }

    const applyUpdatedBasket = async (nextBasket: NonNullable<typeof basket>) => {
        setBasketSnapshot(nextBasket)
        await reloadCheckoutOptions({ showLoading: false })
    }

    const updateCheckoutMeta = async (payload: Parameters<typeof updateOrderDraft>[1]) => {
        const updatesRecipient = "recipient_id" in payload || "new_recipient" in payload
        if (isBasketCheckout) {
            const nextBasket = isAuthenticated
                ? await updateBasketCheckout(payload)
                : await updateGuestBasketCheckout(payload)
            if (updatesRecipient) {
                confirmRecipient(nextBasket.recipient)
                setBasketSnapshot(nextBasket)
                setCheckoutOptions((options) => updateSavedRecipientOptions(options, nextBasket.recipient))
            } else {
                await applyUpdatedBasket(nextBasket)
            }
            return
        }

        const updatedDraft = await updateOrderDraft(orderDraft.id, payload)
        if (updatesRecipient) {
            confirmRecipient(updatedDraft.recipient)
            setOrderDraftSnapshot(updatedDraft)
            setCheckoutOptions((options) => updateSavedRecipientOptions(options, updatedDraft.recipient))
        } else {
            await applyUpdatedDraft(updatedDraft)
        }
    }

    const syncDraftItemsFromBasket = async () => {
        if (isBasketCheckout) {
            await reloadBasket({ showLoading: false })
            return
        }

        const updatedDraft = await updateOrderDraft(orderDraft.id, {
            sync_basket_items: true,
        })

        clearBasketSnapshot()
        await applyUpdatedDraft(updatedDraft)
    }

    const openDraftDiscoverForEditing = () => {
        if (isBasketCheckout) {
            setSelectedDeliveryCountry(orderDraft.delivery_address?.country_code ?? null)
            setSelectedDeliveryAddress(null)
            setSelectedDeliveryPoint(null)
            router.push(ROUTES.discover)
            return
        }

        setBasketDraftEditingId(orderDraft.id)
        setOrderDraftSnapshot(orderDraft)
        setSelectedDeliveryCountry(orderDraft.delivery_address?.country_code ?? null)
        setSelectedDeliveryAddress(null)
        setSelectedDeliveryPoint(null)
        router.push(ROUTES.discover)
    }

    const openDeliveryFromCheckout = () => {
        router.push({
            params: isBasketCheckout ? {} : { draftId: String(orderDraft.id) },
            pathname: ROUTES.delivery,
        })
    }

    const handleAddProductsToDraft = async (options?: { saveCurrentCart?: boolean }) => {
        if (isPositionsBusy) {
            return
        }

        try {
            if (options?.saveCurrentCart) {
                await createOrderDraft({
                    ...buildDraftPayloadFromOrderDraft(orderDraft),
                    draft_name: formatSavedCartDraftName(new Date()),
                })
            }
            await restoreDraft(orderDraft.id)
            Alert.alert(
                t("checkout.editViaBasketTitle"),
                t("checkout.editViaBasketMessage"),
                [
                    {
                        text: t("checkout.openCatalog"),
                        onPress: () => {
                            openDraftDiscoverForEditing()
                        },
                    },
                ],
            )
        } catch (restoreError) {
            Alert.alert(
                options?.saveCurrentCart
                    ? getDraftUpdateErrorMessage(restoreError, t("checkout.saveCurrentCartFailed"))
                    : getBasketErrorMessage(restoreError, basketError, t),
            )
        }
    }

    const handleAddProductsPress = () => {
        if (isBasketCheckout) {
            openDraftDiscoverForEditing()
            return
        }

        if (basketMatchesDraft(basket, orderDraft)) {
            openDraftDiscoverForEditing()
            return
        }

        if (!basket?.items.length) {
            void handleAddProductsToDraft()
            return
        }

        Alert.alert(
            t("checkout.addProductsConfirmTitle"),
            t("checkout.addProductsConfirmMessage"),
            [
                {
                    text: t("common.cancel"),
                    style: "cancel",
                },
                {
                    text: t("checkout.saveCurrentCart"),
                    onPress: () => {
                        void handleAddProductsToDraft({ saveCurrentCart: true })
                    },
                },
                {
                    text: t("checkout.clearCurrentCart"),
                    style: "destructive",
                    onPress: () => {
                        void handleAddProductsToDraft()
                    },
                },
            ],
        )
    }

    const handleDraftItemQuantityCommit = async (
        item: OrderDraftItemRead,
        nextQuantity: number,
        options?: { saveCurrentCart?: boolean },
    ) => {
        if (nextQuantity < 1 || isPositionsBusy) {
            return
        }

        setIsUpdatingPositions(true)

        try {
            if (isBasketCheckout) {
                const nextBasket = isAuthenticated
                    ? await updateBasketItem(item.id, { quantity: nextQuantity })
                    : await updateGuestCartItemQuantity(item.id, nextQuantity)
                setBasketSnapshot(nextBasket)
                return
            }

            if (options?.saveCurrentCart) {
                await createOrderDraft({
                    ...buildDraftPayloadFromOrderDraft(orderDraft),
                    draft_name: formatSavedCartDraftName(new Date()),
                })
            }

            const editableBasket = basketMatchesDraft(basket, orderDraft)
                ? basket
                : await restoreDraftToBasket(orderDraft.id)
            const basketItem = editableBasket?.items.find((basketPosition) => basketPosition.variant_id === item.variant_id)

            if (!basketItem) {
                throw new Error(t("cart.itemMissing"))
            }

            await updateBasketItem(basketItem.id, { quantity: nextQuantity })
            await syncDraftItemsFromBasket()
        } catch (updateError) {
            Alert.alert(getBasketErrorMessage(updateError, basketError, t))
        } finally {
            setIsUpdatingPositions(false)
        }
    }

    const handleDraftItemQuantityChange = (item: OrderDraftItemRead, delta: -1 | 1) => {
        if (isPositionsBusy) {
            return
        }

        const nextQuantity = item.quantity + delta
        if (nextQuantity < 1) {
            return
        }

        if (isBasketCheckout) {
            void handleDraftItemQuantityCommit(item, nextQuantity)
            return
        }

        if (basketMatchesDraft(basket, orderDraft) || !basket?.items.length) {
            void handleDraftItemQuantityCommit(item, nextQuantity)
            return
        }

        Alert.alert(
            t("checkout.addProductsConfirmTitle"),
            t("checkout.addProductsConfirmMessage"),
            [
                {
                    text: t("common.cancel"),
                    style: "cancel",
                },
                {
                    text: t("checkout.saveCurrentCart"),
                    onPress: () => {
                        void handleDraftItemQuantityCommit(item, nextQuantity, { saveCurrentCart: true })
                    },
                },
                {
                    text: t("checkout.clearCurrentCart"),
                    style: "destructive",
                    onPress: () => {
                        void handleDraftItemQuantityCommit(item, nextQuantity)
                    },
                },
            ],
        )
    }

    const handleSelectRecipient = async (option: DeliveryRecipientRead | null) => {
        if (isSavingRecipient) return
        const recipientId = option?.id ?? null
        closeCheckoutPicker()
        if (recipientId === (savedRecipient?.id ?? null)) return

        setIsSavingRecipient(true)

        try {
            await updateCheckoutMeta({
                recipient_id: recipientId,
            })
        } catch (saveError) {
            Alert.alert(getDraftUpdateErrorMessage(saveError, t("checkout.saveDraftMetaFailed")))
        } finally {
            setIsSavingRecipient(false)
        }
    }

    const handleSaveRecipient = async () => {
        if (isSavingRecipient) return
        setRecipientSaveError(null)
        const errors = getRecipientFormErrors(recipientForm, t)
        const fields = [
            ["firstName", recipientFirstNameInputRef],
            ["lastName", recipientLastNameInputRef],
            ["phone", recipientPhoneInputRef],
            ["email", recipientEmailInputRef],
        ] as const
        const invalidField = fields.find(([field]) => showRecipientField(field) && errors[field])
        if (invalidField) {
            setRecipientFormErrors(errors)
            invalidField[1].current?.focus()
            return
        }

        Keyboard.dismiss()
        if (profileFieldsToComplete) {
            setIsSavingRecipient(true)
            try {
                await updatePersonalData(getProfileRecipientUpdate(recipientForm, profileFieldsToComplete))
                handleCloseRecipientEditor()
                void reloadCheckoutOptions({ showLoading: false })
            } catch (saveError) {
                setRecipientSaveError(getDraftUpdateErrorMessage(saveError, t("checkout.recipientSaveFailed")))
            } finally {
                setIsSavingRecipient(false)
            }
            return
        }
        const firstName = recipientForm.firstName.trim()
        const lastName = recipientForm.lastName.trim()
        const phone = normalizePhoneValue(recipientForm.phone)
        const email = recipientForm.email.trim().toLowerCase()

        setIsSavingRecipient(true)

        try {
            if (!isAuthenticated) {
                const phoneCheck = await checkGuestPhone(phone)
                if (phoneCheck.exists) {
                    Alert.alert(
                        t("checkout.existingPhoneTitle"),
                        t("checkout.existingPhoneMessage"),
                        [
                            {
                                text: t("checkout.existingPhoneClear"),
                                style: "cancel",
                                onPress: () => {
                                    setRecipientForm((current) => ({ ...current, phone: "" }))
                                    setRecipientFormErrors((current) => ({ ...current, phone: undefined }))
                                },
                            },
                            {
                                text: t("auth.entry.login"),
                                onPress: () => {
                                    setIsRecipientEditorOpen(false)
                                    router.push(ROUTES.login)
                                },
                            },
                        ],
                    )
                    return
                }
            }

            await updateCheckoutMeta({
                new_recipient: {
                    name: firstName,
                    surname: lastName,
                    phone,
                    email,
                },
            })
            handleCloseRecipientEditor()
        } catch (saveError) {
            setRecipientSaveError(getDraftUpdateErrorMessage(saveError, t("checkout.recipientSaveFailed")))
        } finally {
            setIsSavingRecipient(false)
        }
    }

    const handleSelectAddress = async (deliveryAddressId: number) => {
        if (isSavingAddress) {
            return
        }

        setIsSavingAddress(true)

        try {
            const selectedAddress = availableAddresses.find((address) => address.id === deliveryAddressId)

            if (!selectedAddress) {
                throw new Error(t("checkout.saveDraftMetaFailed"))
            }

            const deliveryCalculation = await calculateDeliveryForSavedAddress(
                selectedAddress,
                isBasketCheckout ? null : orderDraft.id,
            )
            await updateCheckoutMeta({
                new_delivery_address: buildAddressUpdatePayloadWithCalculation(
                    selectedAddress,
                    deliveryCalculation,
                ),
            })
        } catch (saveError) {
            Alert.alert(getDraftUpdateErrorMessage(saveError, t("checkout.saveDraftMetaFailed")))
        } finally {
            setIsSavingAddress(false)
        }
    }

    return (
        <View style={checkoutScreenStyles.container}>
                <ScrollView
                    alwaysBounceVertical
                    contentContainerStyle={checkoutScreenStyles.content}
                    keyboardDismissMode="on-drag"
                    keyboardShouldPersistTaps="handled"
                    onScroll={handleRecommendationsScroll}
                    scrollEventThrottle={16}
                    scrollEnabled
                    style={checkoutScreenStyles.scrollView}
                >
                    <View style={checkoutScreenStyles.detailsSheetCard}>
                        <Pressable
                            accessibilityRole="button"
                            onPress={() => {
                                handleOpenPicker("recipient")
                            }}
                            style={({ pressed }) => [
                                checkoutScreenStyles.detailsSheetRow,
                                pressed && checkoutScreenStyles.detailsSheetRowPressed,
                            ]}
                        >
                            <Text numberOfLines={1} style={checkoutScreenStyles.detailsSheetLabel}>
                                {t("checkout.recipientTitle")}
                            </Text>
                            <View style={checkoutScreenStyles.detailsSheetTrailing}>
                                <View style={checkoutScreenStyles.detailsSheetTextBlock}>
                                    <Text numberOfLines={1} style={checkoutScreenStyles.detailsSheetPrimary}>
                                        {recipientPrimaryText}
                                    </Text>
                                </View>
                            </View>
                        </Pressable>

                        <View style={checkoutScreenStyles.detailsSheetDivider} />

                        <Pressable
                            accessibilityRole="button"
                            onPress={() => {
                                handleOpenPicker("address")
                            }}
                            style={({ pressed }) => [
                                checkoutScreenStyles.detailsSheetRow,
                                pressed && checkoutScreenStyles.detailsSheetRowPressed,
                            ]}
                        >
                            <Text numberOfLines={1} style={checkoutScreenStyles.detailsSheetLabel}>
                                {t("checkout.addressSectionTitle")}
                            </Text>
                            <View style={checkoutScreenStyles.detailsSheetTrailing}>
                                <View style={checkoutScreenStyles.detailsSheetTextBlock}>
                                    <Text numberOfLines={3} style={checkoutScreenStyles.detailsSheetPrimary}>
                                        {orderDraft.delivery_address?.full_address ?? t("checkout.openDelivery")}
                                    </Text>
                                </View>
                            </View>
                        </Pressable>

                        {isAuthenticated ? (
                            <>
                                <View style={checkoutScreenStyles.detailsSheetDivider} />
                                {Number(benefitCheck?.cashback_percent) > 0 ? <View style={checkoutScreenStyles.rewardModeSection}>
                                    <Text style={checkoutScreenStyles.rewardModeTitle}>
                                        {t("checkout.rewardCashbackTitle").replace("{percent}", String(Number(benefitCheck?.cashback_percent)))}
                                    </Text>
                                    <Text style={checkoutScreenStyles.rewardModeOptionHint}>
                                        {benefitCheck && benefitCheck.cashback_earned_points > 0
                                            ? t("checkout.rewardCashbackPreview").replace("{points}", String(benefitCheck.cashback_earned_points))
                                            : t("checkout.rewardCashbackHint")}
                                    </Text>
                                </View> : null}
                                {(!programLocked || hasAttachedPromoCode) ? (
                                    <>
                                        <View style={checkoutScreenStyles.detailsSheetDivider} />
                                        <View style={checkoutScreenStyles.detailsSheetRow}>
                                                <Text numberOfLines={1} style={checkoutScreenStyles.detailsSheetLabel}>
                                                    {t("checkout.promoCodeTitle")}
                                                </Text>
                                                <View style={checkoutScreenStyles.detailsSheetTrailing}>
                                                    <View style={checkoutScreenStyles.detailsSheetTextBlock}>
                                                        <TextInput
                                                            autoCapitalize="characters"
                                                            autoCorrect={false}
                                                            editable={!programLocked && !hasAttachedPromoCode}
                                                            onChangeText={handlePromoCodeChange}
                                                            placeholder={t("checkout.promoCodePlaceholder")}
                                                            placeholderTextColor="#94A3B8"
                                                            style={checkoutScreenStyles.detailsSheetInput}
                                                            value={displayedPromoCode}
                                                        />
                                                    </View>
                                                </View>
                                        </View>
                                    </>
                                ) : null}
                                {benefitCheck?.welcome_expires_at && Number(benefitCheck.welcome_balance_rubles) > 0 ? (
                                    <View style={checkoutScreenStyles.rewardModeSection}>
                                        <Text style={checkoutScreenStyles.rewardModeTitle}>{t("checkout.welcomeBonusTitle")}: {formatMoney(Number(benefitCheck.welcome_balance_rubles), "RUB")}</Text>
                                        <Text style={checkoutScreenStyles.rewardModeOptionHint}>{t("checkout.welcomeBonusTerms")} {new Date(benefitCheck.welcome_expires_at).toLocaleString(language === "kz" ? "kk-KZ" : language, {dateStyle:"medium", timeStyle:"short"})}</Text>
                                    </View>
                                ) : null}
                            </>
                        ) : null}
                    </View>

                    <View style={[checkoutScreenStyles.sectionCard, checkoutScreenStyles.positionsSectionCard]}>
                        <View style={checkoutScreenStyles.sectionHeader}>
                            <Text style={checkoutScreenStyles.sectionHeaderTitle}>
                                {t("checkout.positionsTitle")}
                            </Text>
                        </View>
                        <ScrollView
                            alwaysBounceVertical={false}
                            directionalLockEnabled
                            horizontal
                            nestedScrollEnabled
                            contentContainerStyle={checkoutScreenStyles.positionsCarouselContent}
                            keyboardShouldPersistTaps="handled"
                            scrollEnabled
                            showsHorizontalScrollIndicator={false}
                            style={checkoutScreenStyles.positionsCarousel}
                        >
                            <Pressable
                                accessibilityLabel={t("checkout.addProductsToDraft")}
                                accessibilityRole="button"
                                disabled={isAddProductsBusy}
                                onPress={() => {
                                    handleAddProductsPress()
                                }}
                                style={({ pressed }) => [
                                    checkoutScreenStyles.positionAddCard,
                                    isAddProductsBusy && checkoutScreenStyles.positionAddCardDisabled,
                                    pressed && !isAddProductsBusy && checkoutScreenStyles.positionAddCardPressed,
                                ]}
                            >
                                <Text style={checkoutScreenStyles.positionAddCardText}>+</Text>
                            </Pressable>

                            {orderDraft.items.map((item) => {
                                const pricedItem = getQuotedItemPrice(item, benefitCheck)
                                const hasItemDiscount = Number(pricedItem.unit_price) < Number(item.unit_price)
                                const lineTotalLabel = formatMoney(Number(pricedItem.line_total), orderDraft.currency)

                                return (
                                    <View key={item.id} style={checkoutScreenStyles.positionCard}>
                                        <Image
                                            source={{ uri: item.image_url }}
                                            style={checkoutScreenStyles.positionImage}
                                            resizeMode="cover"
                                        />
                                        <View style={checkoutScreenStyles.positionInfo}>
                                            <Text numberOfLines={2} style={checkoutScreenStyles.positionTitle}>
                                                {item.product_name}
                                            </Text>
                                            <Text style={checkoutScreenStyles.positionSubtitle}>
                                                {item.variant_name || item.product_sku}
                                            </Text>
                                            {lineTotalLabel ? (
                                                <View>
                                                    <Text style={checkoutScreenStyles.positionPrice}>
                                                        {lineTotalLabel}
                                                    </Text>
                                                    {hasItemDiscount ? <Text style={checkoutScreenStyles.positionOriginalPrice}>
                                                        {formatMoney(Number(item.line_total), orderDraft.currency)}
                                                    </Text> : null}
                                                </View>
                                            ) : null}
                                            <Text style={checkoutScreenStyles.positionSubtitle}>
                                                {formatMoney(Number(pricedItem.unit_price), orderDraft.currency)}{t("cart.unitPriceSuffix")}
                                            </Text>
                                            <View style={checkoutScreenStyles.positionQuantityControl}>
                                                <Pressable
                                                    accessibilityLabel={t("cart.decreaseQuantity")}
                                                    accessibilityRole="button"
                                                    disabled={isPositionsBusy || item.quantity <= 1}
                                                    onPress={() => {
                                                        handleDraftItemQuantityChange(item, -1)
                                                    }}
                                                    style={({ pressed }) => [
                                                        checkoutScreenStyles.positionQuantityButton,
                                                        (isPositionsBusy || item.quantity <= 1) &&
                                                            checkoutScreenStyles.positionQuantityButtonDisabled,
                                                        pressed &&
                                                            !(isPositionsBusy || item.quantity <= 1) &&
                                                            checkoutScreenStyles.positionQuantityButtonPressed,
                                                    ]}
                                                >
                                                    <Text style={checkoutScreenStyles.positionQuantityButtonText}>−</Text>
                                                </Pressable>

                                                <Text style={checkoutScreenStyles.positionQuantityValue}>
                                                    {item.quantity}
                                                </Text>

                                                <Pressable
                                                    accessibilityLabel={t("cart.increaseQuantity")}
                                                    accessibilityRole="button"
                                                    disabled={isPositionsBusy}
                                                    onPress={() => {
                                                        handleDraftItemQuantityChange(item, 1)
                                                    }}
                                                    style={({ pressed }) => [
                                                        checkoutScreenStyles.positionQuantityButton,
                                                        isPositionsBusy && checkoutScreenStyles.positionQuantityButtonDisabled,
                                                        pressed &&
                                                            !isPositionsBusy &&
                                                            checkoutScreenStyles.positionQuantityButtonPressed,
                                                    ]}
                                                >
                                                    <Text style={checkoutScreenStyles.positionQuantityButtonText}>+</Text>
                                                </Pressable>
                                            </View>
                                        </View>
                                    </View>
                                )
                            })}
                        </ScrollView>
                    </View>

                    {recommendationRailProducts.length ? (
                        <ContentRail
                            title={t("recommendations.title")}
                            description={t("recommendations.productDescription")}
                            layout="grid"
                            gridVariant="discover"
                            mergeHeaderWithFirstRow
                            loadingMore={recommendationRailLoadingMore}
                            products={recommendationRailProducts}
                        />
                    ) : null}

                </ScrollView>

                <Modal
                    animationType="fade"
                    onRequestClose={isRecipientEditorOpen ? handleCloseRecipientEditor : closeCheckoutPicker}
                    transparent
                    visible={openPickerSection !== null || isRecipientEditorOpen}
                >
                    {!isRecipientEditorOpen ? <AppPickerPanel title={openPickerSection === "recipient" ? t("checkout.recipientTitle") : t("checkout.addressSectionTitle")} onCancel={closeCheckoutPicker}>
                            {optionsLoading ? (
                                <View style={checkoutScreenStyles.selectorLoadingRow}>
                                    <ActivityIndicator size="small" />
                                </View>
                            ) : openPickerSection === "recipient" ? (
                                <Picker
                                    key="checkout-recipient"
                                    accessibilityLabel={t("checkout.recipientTitle")}
                                    selectedValue={recipientPickerValue}
                                    enabled={!isSavingRecipient}
                                    onValueChange={(value) => {
                                        if (isSavingRecipient) return
                                        const action = resolveRecipientPickerAction(
                                            value, recipientPickerValue, availableRecipients, Boolean(selfRecipient),
                                        )
                                        if (action?.type === "add") handleOpenRecipientEditor()
                                        if (action?.type === "select") void handleSelectRecipient(action.recipient)
                                    }}
                                    style={contentStyles.browsePicker}
                                >
                                    {!selfRecipient && !savedRecipient ? (
                                        <Picker.Item label={t("checkout.selectRecipient")} value={NO_RECIPIENT_VALUE} />
                                    ) : null}
                                    {selfRecipient ? (
                                        <Picker.Item label={t("checkout.recipientForMyself")} value={SELF_RECIPIENT_VALUE} />
                                    ) : null}
                                    {availableRecipients.map((option) => (
                                        <Picker.Item key={option.id} label={recipientPickerLabel(option, availableRecipients)} value={option.id} />
                                    ))}
                                    <Picker.Item label={t("checkout.recipientAddNew")} value={ADD_NEW_RECIPIENT_VALUE} />
                                </Picker>
                            ) : (
                                <CheckoutAddressPicker
                                    addresses={availableAddresses}
                                    selectedValue={draftAddressValue}
                                    onSelect={(nextValue) => {
                                        setDraftAddressValue(nextValue === ADD_NEW_ADDRESS_VALUE ? NO_ADDRESS_VALUE : nextValue)
                                        closeCheckoutPicker()

                                        if (nextValue === ADD_NEW_ADDRESS_VALUE) {
                                            setSelectedDeliveryCountry(
                                                orderDraft.delivery_address?.country_code ?? null,
                                            )
                                            setSelectedDeliveryAddress(null)
                                            setSelectedDeliveryPoint(null)
                                            setTimeout(openDeliveryFromCheckout, 0)
                                            return
                                        }

                                        setSelectedAddressValue(nextValue)
                                        setTimeout(() => {
                                            void handleSelectAddress(nextValue)
                                        }, 0)
                                    }}
                                    style={contentStyles.browsePicker}
                                />
                            )}
                    </AppPickerPanel> : (
                    <AppFormLayout
                        style={[contentStyles.browsePickerBackdrop, { paddingTop: topInset + spacing.sm }]}
                    >
                        <Pressable
                            accessibilityRole="button"
                            onPress={handleCloseRecipientEditor}
                            style={contentStyles.browsePickerDismissArea}
                        />

                        <View
                            style={[
                                contentStyles.browsePickerSheet,
                                checkoutScreenStyles.recipientEditorSheet,
                                { paddingBottom: Math.max(spacing.lg, bottomInset + spacing.sm) },
                            ]}
                        >
                            <View style={checkoutScreenStyles.recipientEditorHeader}>
                                <Text numberOfLines={2} style={checkoutScreenStyles.recipientEditorTitle}>
                                    {recipientEditorTitle}
                                </Text>

                                <Pressable
                                    accessibilityLabel={t("common.close")}
                                    accessibilityRole="button"
                                    onPress={handleCloseRecipientEditor}
                                    style={({ pressed }) => [
                                        checkoutScreenStyles.recipientEditorCloseButton,
                                        pressed && checkoutScreenStyles.recipientEditorCloseButtonPressed,
                                    ]}
                                >
                                    <Text style={checkoutScreenStyles.recipientEditorCloseText}>×</Text>
                                </Pressable>
                            </View>

                            <ScrollView
                                contentContainerStyle={checkoutScreenStyles.recipientEditorScrollContent}
                                keyboardDismissMode={Platform.OS === "ios" ? "interactive" : "on-drag"}
                                keyboardShouldPersistTaps="always"
                                onScroll={(event) => {
                                    recipientEditorScrollOffsetRef.current = event.nativeEvent.contentOffset.y
                                }}
                                ref={recipientEditorScrollRef}
                                scrollEventThrottle={16}
                                showsVerticalScrollIndicator={false}
                                style={checkoutScreenStyles.recipientEditorScroll}
                            >
                                <View style={checkoutScreenStyles.recipientEditorFields}>
                                    {showRecipientField("firstName") ? <View style={checkoutScreenStyles.recipientEditorFieldWrap}>
                                        <TextInput
                                            autoCapitalize="words"
                                            onChangeText={(value) => {
                                                setRecipientForm((current) => ({ ...current, firstName: value }))
                                                setRecipientFormErrors((current) => ({ ...current, firstName: undefined }))
                                            }}
                                            onFocus={() => {
                                                handleRecipientInputFocus(recipientFirstNameInputRef.current)
                                            }}
                                            placeholder={t("checkout.recipientNamePlaceholder")}
                                            placeholderTextColor={palette.mutedText}
                                            ref={recipientFirstNameInputRef}
                                            style={[
                                                checkoutScreenStyles.recipientEditorInput,
                                                recipientFormErrors.firstName && checkoutScreenStyles.recipientEditorInputError,
                                            ]}
                                            value={recipientForm.firstName}
                                        />
                                        {recipientFormErrors.firstName ? (
                                            <Text style={checkoutScreenStyles.recipientEditorFieldError}>
                                                {recipientFormErrors.firstName}
                                            </Text>
                                        ) : null}
                                    </View> : null}
                                    {showRecipientField("lastName") ? <View style={checkoutScreenStyles.recipientEditorFieldWrap}>
                                        <TextInput
                                            autoCapitalize="words"
                                            onChangeText={(value) => {
                                                setRecipientForm((current) => ({ ...current, lastName: value }))
                                                setRecipientFormErrors((current) => ({ ...current, lastName: undefined }))
                                            }}
                                            onFocus={() => {
                                                handleRecipientInputFocus(recipientLastNameInputRef.current)
                                            }}
                                            placeholder={t("checkout.recipientSurnamePlaceholder")}
                                            placeholderTextColor={palette.mutedText}
                                            ref={recipientLastNameInputRef}
                                            style={[
                                                checkoutScreenStyles.recipientEditorInput,
                                                recipientFormErrors.lastName && checkoutScreenStyles.recipientEditorInputError,
                                            ]}
                                            value={recipientForm.lastName}
                                        />
                                        {recipientFormErrors.lastName ? (
                                            <Text style={checkoutScreenStyles.recipientEditorFieldError}>
                                                {recipientFormErrors.lastName}
                                            </Text>
                                        ) : null}
                                    </View> : null}
                                    {showRecipientField("phone") ? <View style={checkoutScreenStyles.recipientEditorFieldWrap}>
                                        <TextInput
                                            autoComplete="tel"
                                            keyboardType="phone-pad"
                                            onChangeText={(value) => {
                                                setRecipientForm((current) => ({ ...current, phone: value }))
                                                setRecipientFormErrors((current) => ({ ...current, phone: undefined }))
                                            }}
                                            onFocus={() => {
                                                handleRecipientInputFocus(recipientPhoneInputRef.current)
                                            }}
                                            placeholder={t("checkout.recipientPhonePlaceholder")}
                                            placeholderTextColor={palette.mutedText}
                                            ref={recipientPhoneInputRef}
                                            style={[
                                                checkoutScreenStyles.recipientEditorInput,
                                                recipientFormErrors.phone && checkoutScreenStyles.recipientEditorInputError,
                                            ]}
                                            textContentType="telephoneNumber"
                                            value={recipientForm.phone}
                                        />
                                        {recipientFormErrors.phone ? (
                                            <Text style={checkoutScreenStyles.recipientEditorFieldError}>
                                                {recipientFormErrors.phone}
                                            </Text>
                                        ) : null}
                                    </View> : null}
                                    {showRecipientField("email") ? <View style={checkoutScreenStyles.recipientEditorFieldWrap}>
                                        <TextInput
                                            autoCapitalize="none"
                                            autoComplete="email"
                                            keyboardType="email-address"
                                            onChangeText={(value) => {
                                                setRecipientForm((current) => ({ ...current, email: value }))
                                                setRecipientFormErrors((current) => ({ ...current, email: undefined }))
                                            }}
                                            onFocus={() => {
                                                handleRecipientInputFocus(recipientEmailInputRef.current)
                                            }}
                                            placeholder={t("checkout.recipientEmailPlaceholder")}
                                            placeholderTextColor={palette.mutedText}
                                            ref={recipientEmailInputRef}
                                            style={[
                                                checkoutScreenStyles.recipientEditorInput,
                                                recipientFormErrors.email && checkoutScreenStyles.recipientEditorInputError,
                                            ]}
                                            textContentType="emailAddress"
                                            value={recipientForm.email}
                                        />
                                        {recipientFormErrors.email ? (
                                            <Text style={checkoutScreenStyles.recipientEditorFieldError}>
                                                {recipientFormErrors.email}
                                            </Text>
                                        ) : null}
                                    </View> : null}
                                </View>

                                {recipientSaveError ? (
                                    <Text accessibilityRole="alert" style={checkoutScreenStyles.recipientEditorFieldError}>
                                        {recipientSaveError}
                                    </Text>
                                ) : null}
                                <Pressable
                                    accessibilityLabel={recipientSaveLabel}
                                    accessibilityRole="button"
                                    accessibilityState={{ busy: isSavingRecipient, disabled: isSavingRecipient }}
                                    disabled={isSavingRecipient}
                                    onPress={() => {
                                        void handleSaveRecipient()
                                    }}
                                    style={({ pressed }) => [
                                        checkoutScreenStyles.recipientEditorSubmitButton,
                                        isSavingRecipient && checkoutScreenStyles.recipientEditorSubmitButtonDisabled,
                                        pressed && !isSavingRecipient && checkoutScreenStyles.recipientEditorSubmitButtonPressed,
                                    ]}
                                >
                                    {isSavingRecipient ? <ActivityIndicator color={palette.mutedText} /> : (
                                        <Text style={checkoutScreenStyles.recipientEditorSubmitButtonText}>
                                            {recipientSaveLabel}
                                        </Text>
                                    )}
                                </Pressable>
                            </ScrollView>
                        </View>
                    </AppFormLayout>
                    )}
                </Modal>
            </View>
    )
}
