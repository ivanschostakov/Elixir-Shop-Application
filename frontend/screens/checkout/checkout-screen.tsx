import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react"
import { Picker } from "@react-native-picker/picker"
import {
    ActivityIndicator,
    Alert,
    Image,
    Keyboard,
    Modal,
    type NativeScrollEvent,
    type NativeSyntheticEvent,
    Pressable,
    ScrollView,
    Text,
    TextInput,
    View,
} from "react-native"
import { router, useFocusEffect, useLocalSearchParams } from "expo-router"

import { ContentRail } from "@/components/content/content-rail"
import { contentStyles } from "@/components/content/content.styles"
import {
    setSelectedDeliveryAddress,
} from "@/hooks/delivery/delivery-address-selection-store"
import { clearBasketSnapshot } from "@/hooks/basket/basket-store"
import { useBasket } from "@/hooks/basket/use-basket"
import { setBasketDraftEditingId } from "@/hooks/basket/basket-draft-editing-store"
import { useBasketMutations } from "@/hooks/basket/use-basket-mutations"
import { setSelectedDeliveryCountry } from "@/hooks/delivery/delivery-country-selection-store"
import { setSelectedDeliveryPoint } from "@/hooks/delivery/delivery-point-selection-store"
import { setOrderDraftSnapshot } from "@/hooks/order-draft/order-draft-store"
import { useOrderDraft } from "@/hooks/order-draft/use-order-draft"
import { useRecommendations } from "@/hooks/recommendations/use-recommendations"
import { useAsyncData } from "@/hooks/shared/use-async-data"
import { useApplyScreenTemplate } from "@/components/templates/screen-template.hooks"
import { ROUTES } from "@/constants/routes"
import { useAuth } from "@/providers/auth-provider"
import { useLanguage } from "@/providers/language-provider"
import { getBasketErrorMessage } from "@/screens/cart/cart-screen.utils"
import {
    ADD_NEW_ADDRESS_VALUE,
    ADD_NEW_RECIPIENT_VALUE,
    SELF_RECIPIENT_VALUE,
} from "@/screens/checkout/checkout-screen.constants"
import { checkoutScreenStyles } from "@/screens/checkout/checkout-screen.styles"
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
    buildDraftPayloadFromOrderDraft,
    createEmptyRecipientForm,
    formatMoney,
    formatRecipientName,
    formatSavedCartDraftName,
    getDraftRecipient,
    getSelfRecipient,
    getDraftUpdateErrorMessage,
    getRecipientFormFromRecipient,
    hasRecipientErrors,
    isValidEmail,
    isValidPhone,
    normalizePhoneValue,
    normalizeTextInputValue,
    parseDraftId,
} from "@/screens/checkout/checkout-screen.utils"
import { restoreDraftToBasket, updateBasketItem } from "@/services/api/basket"
import { createOrderDraft, getOrderDraftOptions, updateOrderDraft } from "@/services/api/order-drafts"
import type {
    DeliveryRecipientRead,
    OrderDraftCheckoutOptionsRead,
    OrderDraftItemRead,
    OrderDraftRead,
} from "@/services/api/order-drafts.types"
import { colors } from "@/theme/colors"

export default function CheckoutScreen() {
    const { user } = useAuth()
    const { t } = useLanguage()
    const params = useLocalSearchParams<{ draftId?: string | string[] }>()
    const draftId = parseDraftId(params.draftId)
    const { basket } = useBasket()
    const { error: basketError, restoreDraft, updating: isRestoringDraft } = useBasketMutations()
    const { orderDraft, error, loading, reload } = useOrderDraft(draftId)
    const {
        hasMore: hasMoreRecommendations,
        loadMore: loadMoreRecommendations,
        loadingMore: recommendationsLoadingMore,
        products: recommendedProducts,
    } = useRecommendations({
        surface: "draft",
        draftId: orderDraft?.id ?? null,
        limit: 6,
        enabled: Boolean(orderDraft?.id && orderDraft.items.length),
        deps: [orderDraft?.updated_at ?? null, orderDraft?.items.length ?? 0],
    })
    const { data: checkoutOptions, loading: optionsLoading, reload: reloadCheckoutOptions } = useAsyncData<OrderDraftCheckoutOptionsRead | null>({
        deps: [orderDraft?.id ?? null],
        enabled: Boolean(orderDraft?.id),
        fetcher: async () => {
            if (!orderDraft?.id) {
                return null
            }

            return getOrderDraftOptions(orderDraft.id)
        },
        initialData: null,
        resetOnLoad: true,
    })
    const [openPickerSection, setOpenPickerSection] = useState<ExpandedSection>(null)
    const [isRecipientEditorOpen, setIsRecipientEditorOpen] = useState(false)
    const [isSavingRecipient, setIsSavingRecipient] = useState(false)
    const [isSavingAddress, setIsSavingAddress] = useState(false)
    const [selectedRecipientKey, setSelectedRecipientKey] = useState<number | typeof SELF_RECIPIENT_VALUE | typeof ADD_NEW_RECIPIENT_VALUE | null>(null)
    const [selectedAddressValue, setSelectedAddressValue] = useState<number | typeof ADD_NEW_ADDRESS_VALUE | null>(null)
    const [draftRecipientKey, setDraftRecipientKey] = useState<number | typeof SELF_RECIPIENT_VALUE | typeof ADD_NEW_RECIPIENT_VALUE | null>(null)
    const [draftAddressValue, setDraftAddressValue] = useState<number | typeof ADD_NEW_ADDRESS_VALUE | null>(null)
    const [recipientForm, setRecipientForm] = useState<RecipientFormState>(createEmptyRecipientForm())
    const [recipientFormErrors, setRecipientFormErrors] = useState<RecipientFormErrors>({})

    useEffect(() => {
        if (!orderDraft) {
            return
        }

        setRecipientForm(getRecipientFormFromRecipient(getDraftRecipient(orderDraft)))
        setRecipientFormErrors({})
    }, [orderDraft])

    useFocusEffect(
        useCallback(() => (
            () => {
                setOpenPickerSection(null)
                setIsRecipientEditorOpen(false)
            }
        ), []),
    )

    const savedRecipient = getDraftRecipient(orderDraft)
    const selfRecipient = getSelfRecipient(user)
    const currentRecipient = savedRecipient ?? selfRecipient
    const deliveryCost = orderDraft
        ? formatMoney(Number(orderDraft.delivery_total), orderDraft.currency)
        : null
    const basketSubtotal = orderDraft
        ? formatMoney(Number(orderDraft.basket_subtotal), orderDraft.currency)
        : null
    const grandTotal = orderDraft
        ? formatMoney(Number(orderDraft.grand_total), orderDraft.currency)
        : null
    const hasDeliveryAddress = Boolean(orderDraft?.delivery_address)
    const hasRecipient = Boolean(currentRecipient)
    const payCtaLabel = grandTotal
        ? `${t("checkout.payCta")} ${grandTotal}`
        : t("checkout.payCta")
    const checkoutFooterCtaLabel = !hasDeliveryAddress
        ? t("checkout.openDelivery")
        : !hasRecipient
            ? t("checkout.selectRecipient")
            : payCtaLabel
    const isCheckoutFooterCtaDisabled = !hasDeliveryAddress || !hasRecipient
    const [isUpdatingPositions, setIsUpdatingPositions] = useState(false)
    const isPositionsBusy = isRestoringDraft || isUpdatingPositions
    const isAddProductsBusy = isRestoringDraft
    const openPaymentFlow = useCallback((paymentMethod: "later" | "sbp") => {
        if (!orderDraft) {
            return
        }

        router.push({
            pathname: ROUTES.payment,
            params: {
                draftId: String(orderDraft.id),
                paymentMethod,
            },
        })
    }, [orderDraft])

    const handlePressPay = useCallback(() => {
        Alert.alert(t("checkout.paymentMethodTitle"), undefined, [
            {
                text: t("checkout.paymentMethodCancel"),
                style: "cancel",
            },
            {
                text: t("payment.methodLaterTitle"),
                style: "destructive",
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

    const checkoutChromeTemplate = useMemo(() => {
        if (!orderDraft) {
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
                            onPress={handlePressPay}
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
    }, [basketSubtotal, checkoutFooterCtaLabel, deliveryCost, grandTotal, handlePressPay, isCheckoutFooterCtaDisabled, orderDraft, t])
    useApplyScreenTemplate("feed", checkoutChromeTemplate)
    const recipientPrimaryText = savedRecipient ? formatRecipientName(savedRecipient) : t("checkout.recipientForMyself")
    const availableRecipients = useMemo(() => {
        return orderDraft ? buildAvailableRecipients(orderDraft, checkoutOptions) : []
    }, [checkoutOptions, orderDraft])
    const availableAddresses = useMemo(() => {
        return orderDraft ? buildAvailableAddresses(orderDraft, checkoutOptions) : []
    }, [checkoutOptions, orderDraft])
    const firstNameInput = normalizeTextInputValue(recipientForm.firstName)
    const lastNameInput = normalizeTextInputValue(recipientForm.lastName)
    const phoneInput = normalizeTextInputValue(recipientForm.phone)
    const emailInput = normalizeTextInputValue(recipientForm.email)
    const recipientFormValidationErrors: RecipientFormErrors = {
        firstName: firstNameInput ? undefined : t("checkout.recipientFirstNameRequired"),
        lastName: lastNameInput ? undefined : t("checkout.recipientLastNameRequired"),
        phone: !phoneInput
            ? t("checkout.recipientPhoneRequired")
            : (isValidPhone(phoneInput) ? undefined : t("checkout.recipientPhoneInvalid")),
        email: !emailInput
            ? t("checkout.recipientEmailRequired")
            : (isValidEmail(emailInput) ? undefined : t("checkout.recipientEmailInvalid")),
    }
    const isRecipientFormValid = !hasRecipientErrors(recipientFormValidationErrors)

    useEffect(() => {
        if (!orderDraft) {
            return
        }

        if (!savedRecipient) {
            const selfRecipientKey = SELF_RECIPIENT_VALUE
            setSelectedRecipientKey(selfRecipientKey)
            setDraftRecipientKey(selfRecipientKey)
            return
        }

        const activeRecipient = availableRecipients.find((option) => option.id === savedRecipient.id)
        setSelectedRecipientKey(activeRecipient?.id ?? savedRecipient.id)
        setDraftRecipientKey(activeRecipient?.id ?? savedRecipient.id)
    }, [availableRecipients, orderDraft, savedRecipient])

    useEffect(() => {
        if (!orderDraft) {
            return
        }

        if (!orderDraft.delivery_address) {
            setSelectedAddressValue(ADD_NEW_ADDRESS_VALUE)
            setDraftAddressValue(ADD_NEW_ADDRESS_VALUE)
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

    if (loading && !orderDraft) {
        return renderStateScreen(
            <View style={checkoutScreenStyles.stateLoadingRow}>
                <ActivityIndicator />
                <Text style={checkoutScreenStyles.loadingText}>{t("checkout.title")}</Text>
            </View>,
        )
    }

    if (error && !orderDraft) {
        return renderStateScreen(
            <>
                <Text style={checkoutScreenStyles.sectionTitle}>{t("checkout.loadFailedTitle")}</Text>
                <Text style={checkoutScreenStyles.stateText}>{t("checkout.loadFailedMessage")}</Text>
                <View style={[checkoutScreenStyles.actionRow, checkoutScreenStyles.actionRowSingle]}>
                    <Pressable
                        accessibilityLabel={t("checkout.retry")}
                        accessibilityRole="button"
                        onPress={() => {
                            void reload()
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

    const handleOpenPicker = (section: Exclude<ExpandedSection, null>) => {
        Keyboard.dismiss()

        if (section === "recipient") {
            setDraftRecipientKey(selectedRecipientKey ?? savedRecipient?.id ?? SELF_RECIPIENT_VALUE)
        } else {
            setDraftAddressValue(selectedAddressValue ?? orderDraft.delivery_address?.id ?? ADD_NEW_ADDRESS_VALUE)
        }
        setOpenPickerSection(section)
    }

    const closeCheckoutPicker = () => {
        setOpenPickerSection(null)
    }

    const handleOpenRecipientEditor = () => {
        Keyboard.dismiss()
        setRecipientForm(
            savedRecipient
                ? createEmptyRecipientForm()
                : getRecipientFormFromRecipient(selfRecipient),
        )
        setRecipientFormErrors({})
        setIsRecipientEditorOpen(true)
    }

    const handleCloseRecipientEditor = () => {
        Keyboard.dismiss()
        setRecipientFormErrors({})
        setIsRecipientEditorOpen(false)
    }

    const applyUpdatedDraft = async (nextDraft: OrderDraftRead) => {
        setOrderDraftSnapshot(nextDraft)
        await reloadCheckoutOptions({ showLoading: false })
    }

    const syncDraftItemsFromBasket = async () => {
        const updatedDraft = await updateOrderDraft(orderDraft.id, {
            sync_basket_items: true,
        })

        clearBasketSnapshot()
        await applyUpdatedDraft(updatedDraft)
    }

    const openDraftDiscoverForEditing = () => {
        setBasketDraftEditingId(orderDraft.id)
        setOrderDraftSnapshot(orderDraft)
        setSelectedDeliveryCountry(orderDraft.delivery_address?.country_code ?? null)
        setSelectedDeliveryAddress(null)
        setSelectedDeliveryPoint(null)
        router.push(ROUTES.discover)
    }

    const openDeliveryFromCheckout = () => {
        router.push({
            params: { draftId: String(orderDraft.id) },
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
        if (isSavingRecipient) {
            return
        }

        if (option === null) {
            if (orderDraft.recipient_id === null && currentRecipient === null) {
                return
            }

            setIsSavingRecipient(true)

            try {
                const updatedDraft = await updateOrderDraft(orderDraft.id, {
                    recipient_id: null,
                })
                await applyUpdatedDraft(updatedDraft)
            } catch (saveError) {
                Alert.alert(getDraftUpdateErrorMessage(saveError, t("checkout.saveDraftMetaFailed")))
            } finally {
                setIsSavingRecipient(false)
            }
            return
        }

        if (option.id <= 0) {
            return
        }

        setIsSavingRecipient(true)

        try {
            const updatedDraft = await updateOrderDraft(orderDraft.id, {
                recipient_id: option.id,
            })
            await applyUpdatedDraft(updatedDraft)
        } catch (saveError) {
            Alert.alert(getDraftUpdateErrorMessage(saveError, t("checkout.saveDraftMetaFailed")))
        } finally {
            setIsSavingRecipient(false)
        }
    }

    const handleSaveRecipient = async () => {
        if (!isRecipientFormValid) {
            setRecipientFormErrors(recipientFormValidationErrors)
            return
        }

        const firstName = firstNameInput as string
        const lastName = lastNameInput as string
        const phone = normalizePhoneValue(phoneInput as string)
        const email = (emailInput as string).trim().toLowerCase()

        setIsSavingRecipient(true)

        try {
            const updatedDraft = await updateOrderDraft(orderDraft.id, {
                new_recipient: {
                    name: firstName,
                    surname: lastName,
                    phone,
                    email,
                },
            })
            await applyUpdatedDraft(updatedDraft)
            setIsRecipientEditorOpen(false)
        } catch (saveError) {
            Alert.alert(getDraftUpdateErrorMessage(saveError, t("checkout.saveDraftMetaFailed")))
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

            const deliveryCalculation = await calculateDeliveryForSavedAddress(selectedAddress)
            const updatedDraft = await updateOrderDraft(orderDraft.id, {
                new_delivery_address: buildAddressUpdatePayloadWithCalculation(
                    selectedAddress,
                    deliveryCalculation,
                ),
            })
            await applyUpdatedDraft(updatedDraft)
        } catch (saveError) {
            Alert.alert(getDraftUpdateErrorMessage(saveError, t("checkout.saveDraftMetaFailed")))
        } finally {
            setIsSavingAddress(false)
        }
    }

    const handlePickerDone = async () => {
        if (openPickerSection === "recipient") {
            closeCheckoutPicker()

            if (draftRecipientKey === ADD_NEW_RECIPIENT_VALUE) {
                handleOpenRecipientEditor()
                return
            }

            if (draftRecipientKey === SELF_RECIPIENT_VALUE) {
                setSelectedRecipientKey(SELF_RECIPIENT_VALUE)
                await handleSelectRecipient(null)
                return
            }

            if (!draftRecipientKey) {
                return
            }

            const selectedRecipient = availableRecipients.find((option) => option.id === draftRecipientKey)
            if (!selectedRecipient) {
                return
            }

            setSelectedRecipientKey(draftRecipientKey)
            await handleSelectRecipient(selectedRecipient)
            return
        }

        if (openPickerSection === "address") {
            if (draftAddressValue === ADD_NEW_ADDRESS_VALUE) {
                setSelectedDeliveryCountry(orderDraft.delivery_address?.country_code ?? null)
                setSelectedDeliveryAddress(null)
                setSelectedDeliveryPoint(null)
                openDeliveryFromCheckout()
                return
            }

            closeCheckoutPicker()

            if (draftAddressValue === null) {
                return
            }

            setSelectedAddressValue(draftAddressValue)
            await handleSelectAddress(draftAddressValue)
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

                        <View style={checkoutScreenStyles.detailsSheetDivider} />

                        <View style={checkoutScreenStyles.detailsSheetRow}>
                            <Text numberOfLines={1} style={checkoutScreenStyles.detailsSheetLabel}>
                                {t("checkout.promoCodeTitle")}
                            </Text>
                            <View style={checkoutScreenStyles.detailsSheetTrailing}>
                                <View style={checkoutScreenStyles.detailsSheetTextBlock}>
                                    <Text numberOfLines={1} style={checkoutScreenStyles.detailsSheetDisabledText}>
                                        {t("checkout.promoCodeComingSoon")}
                                    </Text>
                                </View>
                            </View>
                        </View>
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
                                const lineTotalLabel = formatMoney(Number(item.line_total), orderDraft.currency)

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
                                                <Text style={checkoutScreenStyles.positionPrice}>
                                                    {lineTotalLabel}
                                                </Text>
                                            ) : null}
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

                    {recommendedProducts.length ? (
                        <ContentRail
                            title={t("recommendations.title")}
                            description={t("recommendations.productDescription")}
                            layout="grid"
                            gridVariant="discover"
                            mergeHeaderWithFirstRow
                            loadingMore={recommendationsLoadingMore}
                            products={recommendedProducts}
                        />
                    ) : null}

                </ScrollView>

                <Modal
                    animationType="fade"
                    onRequestClose={closeCheckoutPicker}
                    transparent
                    visible={openPickerSection !== null}
                >
                    <View style={contentStyles.browsePickerBackdrop}>
                        <Pressable
                            accessibilityRole="button"
                            onPress={closeCheckoutPicker}
                            style={contentStyles.browsePickerDismissArea}
                        />

                        <View style={contentStyles.browsePickerSheet}>
                            <View style={contentStyles.browsePickerHeader}>
                                <Text style={contentStyles.browsePickerTitle}>
                                    {openPickerSection === "recipient"
                                        ? t("checkout.recipientTitle")
                                        : t("checkout.addressSectionTitle")}
                                </Text>

                                <View style={contentStyles.browsePickerActions}>
                                    <Pressable
                                        accessibilityLabel={t("common.cancel")}
                                        accessibilityRole="button"
                                        onPress={closeCheckoutPicker}
                                        style={({ pressed }) => [
                                            contentStyles.browsePickerAction,
                                            pressed && contentStyles.browsePickerActionPressed,
                                        ]}
                                    >
                                        <Text style={contentStyles.browsePickerActionText}>
                                            {t("common.cancel")}
                                        </Text>
                                    </Pressable>

                                    <Pressable
                                        accessibilityLabel={t("common.done")}
                                        accessibilityRole="button"
                                        onPress={() => {
                                            void handlePickerDone()
                                        }}
                                        style={({ pressed }) => [
                                            contentStyles.browsePickerPrimaryAction,
                                            pressed && contentStyles.browsePickerActionPressed,
                                        ]}
                                    >
                                        <Text style={contentStyles.browsePickerPrimaryActionText}>
                                            {t("common.done")}
                                        </Text>
                                    </Pressable>
                                </View>
                            </View>

                            {optionsLoading ? (
                                <View style={checkoutScreenStyles.selectorLoadingRow}>
                                    <ActivityIndicator size="small" />
                                </View>
                            ) : openPickerSection === "recipient" ? (
                                <Picker
                                    selectedValue={draftRecipientKey}
                                    onValueChange={(value) => {
                                        const nextValue =
                                            value === ADD_NEW_RECIPIENT_VALUE
                                                ? ADD_NEW_RECIPIENT_VALUE
                                                : value === SELF_RECIPIENT_VALUE
                                                    ? SELF_RECIPIENT_VALUE
                                                : Number(value)
                                        setDraftRecipientKey(nextValue)

                                        if (nextValue === ADD_NEW_RECIPIENT_VALUE) {
                                            closeCheckoutPicker()
                                            setTimeout(() => {
                                                handleOpenRecipientEditor()
                                            }, 0)
                                            return
                                        }

                                        if (nextValue === SELF_RECIPIENT_VALUE) {
                                            setSelectedRecipientKey(SELF_RECIPIENT_VALUE)
                                            closeCheckoutPicker()
                                            setTimeout(() => {
                                                void handleSelectRecipient(null)
                                            }, 0)
                                        }
                                    }}
                                    style={contentStyles.browsePicker}
                                >
                                    <Picker.Item
                                        key={SELF_RECIPIENT_VALUE}
                                        label={t("checkout.recipientForMyself")}
                                        value={SELF_RECIPIENT_VALUE}
                                    />
                                    {availableRecipients.map((option) => {
                                        return (
                                            <Picker.Item
                                                key={option.id}
                                                label={formatRecipientName(option)}
                                                value={option.id}
                                            />
                                        )
                                    })}
                                    <Picker.Item
                                        label={t("checkout.recipientAddNew")}
                                        value={ADD_NEW_RECIPIENT_VALUE}
                                    />
                                </Picker>
                            ) : (
                                <Picker
                                    selectedValue={draftAddressValue}
                                    onValueChange={(value) => {
                                        setDraftAddressValue(
                                            value === ADD_NEW_ADDRESS_VALUE
                                                ? ADD_NEW_ADDRESS_VALUE
                                                : Number(value),
                                        )
                                    }}
                                    style={contentStyles.browsePicker}
                                >
                                    {availableAddresses.map((address) => (
                                        <Picker.Item
                                            key={address.id}
                                            label={address.full_address}
                                            value={address.id}
                                        />
                                    ))}
                                    <Picker.Item
                                        label={t("checkout.addressAddNew")}
                                        value={ADD_NEW_ADDRESS_VALUE}
                                    />
                                </Picker>
                            )}
                        </View>
                    </View>
                </Modal>

                <Modal
                    animationType="fade"
                    onRequestClose={handleCloseRecipientEditor}
                    transparent
                    visible={isRecipientEditorOpen}
                >
                    <View style={contentStyles.browsePickerBackdrop}>
                        <Pressable
                            accessibilityRole="button"
                            onPress={handleCloseRecipientEditor}
                            style={contentStyles.browsePickerDismissArea}
                        />

                        <View style={[contentStyles.browsePickerSheet, checkoutScreenStyles.recipientEditorSheet]}>
                            <View style={checkoutScreenStyles.recipientEditorHeader}>
                                <Text numberOfLines={2} style={checkoutScreenStyles.recipientEditorTitle}>
                                    {t("checkout.recipientAddNew")}
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

                            <View style={checkoutScreenStyles.recipientEditorFields}>
                                <View style={checkoutScreenStyles.recipientEditorFieldWrap}>
                                    <TextInput
                                        autoCapitalize="words"
                                        onChangeText={(value) => {
                                            setRecipientForm((current) => ({ ...current, firstName: value }))
                                            setRecipientFormErrors((current) => ({ ...current, firstName: undefined }))
                                        }}
                                        placeholder={t("checkout.recipientNamePlaceholder")}
                                        placeholderTextColor={colors.mutedText}
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
                                </View>
                                <View style={checkoutScreenStyles.recipientEditorFieldWrap}>
                                    <TextInput
                                        autoCapitalize="words"
                                        onChangeText={(value) => {
                                            setRecipientForm((current) => ({ ...current, lastName: value }))
                                            setRecipientFormErrors((current) => ({ ...current, lastName: undefined }))
                                        }}
                                        placeholder={t("checkout.recipientSurnamePlaceholder")}
                                        placeholderTextColor={colors.mutedText}
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
                                </View>
                                <View style={checkoutScreenStyles.recipientEditorFieldWrap}>
                                    <TextInput
                                        autoComplete="tel"
                                        keyboardType="phone-pad"
                                        onChangeText={(value) => {
                                            setRecipientForm((current) => ({ ...current, phone: value }))
                                            setRecipientFormErrors((current) => ({ ...current, phone: undefined }))
                                        }}
                                        placeholder={t("checkout.recipientPhonePlaceholder")}
                                        placeholderTextColor={colors.mutedText}
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
                                </View>
                                <View style={checkoutScreenStyles.recipientEditorFieldWrap}>
                                    <TextInput
                                        autoCapitalize="none"
                                        autoComplete="email"
                                        keyboardType="email-address"
                                        onChangeText={(value) => {
                                            setRecipientForm((current) => ({ ...current, email: value }))
                                            setRecipientFormErrors((current) => ({ ...current, email: undefined }))
                                        }}
                                        placeholder={t("checkout.recipientEmailPlaceholder")}
                                        placeholderTextColor={colors.mutedText}
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
                                </View>
                            </View>

                            <Pressable
                                accessibilityLabel={t("checkout.recipientCreateAction")}
                                accessibilityRole="button"
                                disabled={!isRecipientFormValid || isSavingRecipient}
                                onPress={() => {
                                    void handleSaveRecipient()
                                }}
                                style={({ pressed }) => [
                                    checkoutScreenStyles.recipientEditorSubmitButton,
                                    (!isRecipientFormValid || isSavingRecipient)
                                        && checkoutScreenStyles.recipientEditorSubmitButtonDisabled,
                                    pressed
                                        && isRecipientFormValid
                                        && !isSavingRecipient
                                        && checkoutScreenStyles.recipientEditorSubmitButtonPressed,
                                ]}
                            >
                                <Text
                                    style={[
                                        checkoutScreenStyles.recipientEditorSubmitButtonText,
                                        (!isRecipientFormValid || isSavingRecipient)
                                            && checkoutScreenStyles.recipientEditorSubmitButtonTextDisabled,
                                    ]}
                                >
                                    {t("checkout.recipientCreateAction")}
                                </Text>
                            </Pressable>
                        </View>
                    </View>
                </Modal>
            </View>
    )
}
