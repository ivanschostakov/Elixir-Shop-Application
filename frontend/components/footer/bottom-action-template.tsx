import { useState } from "react"
import { Alert, Pressable, Text, View } from "react-native"
import { useLocalSearchParams, usePathname, useRouter } from "expo-router"

import type { BottomActionTemplateProps } from "@/components/footer/bottom-action-template.types"
import {
    getExistingDraftIdFromError,
    parseDraftId,
} from "@/components/footer/bottom-action-template.utils"
import { stickyFooterStyles } from "@/components/footer/sticky-footer.styles"
import { getAddToCartErrorMessage } from "@/components/footer/sticky-footer.utils"
import { ROUTES, getProductIdFromRoute, isProductRoute } from "@/constants/routes"
import { clearBasketSnapshot } from "@/hooks/basket/basket-store"
import { useBasket } from "@/hooks/basket/use-basket"
import { useBasketMutations } from "@/hooks/basket/use-basket-mutations"
import { setOrderDraftSnapshot } from "@/hooks/order-draft/order-draft-store"
import { useRememberedProductVariantSelection } from "@/hooks/products/product-variant-selection-store"
import { useLanguage } from "@/providers/language-provider"
import { ApiError } from "@/services/api/client"
import { createOrderDraft, getOrderDraft, updateOrderDraft } from "@/services/api/order-drafts"
import type { OrderDraftRead } from "@/services/api/order-drafts.types"

export function BottomActionTemplate({ variant }: BottomActionTemplateProps) {
    const pathname = usePathname()
    const router = useRouter()
    const params = useLocalSearchParams<{ draftId?: string | string[] }>()
    const { t } = useLanguage()
    const { basket } = useBasket()
    const [isOpeningCheckout, setIsOpeningCheckout] = useState(false)
    const { addItem, clear, error: basketError, removeItem, updateItemQuantity, updating } = useBasketMutations()
    const basketDraftId = pathname === ROUTES.basket ? parseDraftId(params.draftId) : null
    const currentProductId = isProductRoute(pathname) ? Number(getProductIdFromRoute(pathname)) : null
    const selectedVariant = useRememberedProductVariantSelection(currentProductId)

    const isProductActionDisabled = updating || !selectedVariant?.variantId || selectedVariant.stock <= 0
    const selectedBasketItem = selectedVariant?.variantId
        ? basket?.items.find((item) => item.variant_id === selectedVariant.variantId) ?? null
        : null
    const selectedBasketQuantity = selectedBasketItem?.quantity ?? 0
    const selectedBasketAvailableQuantity = selectedBasketItem?.available_quantity ?? 0
    const canIncreaseSelectedVariant =
        selectedBasketItem !== null &&
        !updating &&
        selectedBasketQuantity < selectedBasketAvailableQuantity &&
        selectedVariant !== null &&
        selectedVariant.stock > 0

    const handleBasketActionError = (error: unknown) => {
        Alert.alert(getAddToCartErrorMessage(error, basketError, t))
    }

    const handleConfirmRemoveSelectedBasketItem = () => {
        if (!selectedBasketItem) {
            return
        }

        Alert.alert(t("cart.removeConfirmTitle"), t("cart.removeConfirmMessage"), [
            {
                text: t("common.cancel"),
                style: "cancel",
            },
            {
                text: t("cart.removeItem"),
                style: "destructive",
                onPress: () => {
                    void removeItem(selectedBasketItem.id).catch(handleBasketActionError)
                },
            },
        ])
    }

    const handleAddToBasketPress = async () => {
        if (!selectedVariant?.variantId || selectedVariant.stock <= 0) {
            return
        }

        try {
            await addItem(selectedVariant.variantId, 1)
        } catch (error) {
            handleBasketActionError(error)
        }
    }

    const handleDecreaseBasketQuantity = async () => {
        if (!selectedBasketItem) {
            return
        }

        if (selectedBasketItem.quantity <= 1) {
            handleConfirmRemoveSelectedBasketItem()
            return
        }

        try {
            await updateItemQuantity(selectedBasketItem.id, selectedBasketItem.quantity - 1)
        } catch (error) {
            handleBasketActionError(error)
        }
    }

    const handleIncreaseBasketQuantity = async () => {
        if (!selectedBasketItem || !canIncreaseSelectedVariant) {
            return
        }

        try {
            await updateItemQuantity(selectedBasketItem.id, selectedBasketItem.quantity + 1)
        } catch (error) {
            handleBasketActionError(error)
        }
    }

    const handleOpenExistingDraftCheckout = async (draft: OrderDraftRead) => {
        await clear()
        setOrderDraftSnapshot(draft)
        router.push(`${ROUTES.checkout}?draftId=${draft.id}`)
    }

    const handleOpenCheckout = async () => {
        if (isOpeningCheckout) {
            return
        }

        setIsOpeningCheckout(true)

        try {
            const nextDraft = basketDraftId !== null
                ? await updateOrderDraft(basketDraftId, { sync_basket_items: true })
                : await createOrderDraft({})

            if (basketDraftId === null) {
                clearBasketSnapshot()
            } else {
                await clear()
            }

            setOrderDraftSnapshot(nextDraft)
            router.push(`${ROUTES.checkout}?draftId=${nextDraft.id}`)
        } catch (error) {
            if (basketDraftId === null && basket?.items.length && error instanceof ApiError && error.status === 409) {
                const existingDraftId = getExistingDraftIdFromError(error)

                if (existingDraftId !== null) {
                    const matchingDraft = await getOrderDraft(existingDraftId)
                    Alert.alert(
                        t("cart.existingDraftTitle"),
                        t("cart.existingDraftMessage"),
                        [
                            {
                                text: t("common.cancel"),
                                style: "cancel",
                            },
                            {
                                text: t("cart.existingDraftAction"),
                                onPress: () => {
                                    void handleOpenExistingDraftCheckout(matchingDraft).catch((nextError) => {
                                        const nextErrorMessage = nextError instanceof ApiError && nextError.message
                                            ? nextError.message
                                            : t("cart.checkoutFailed")
                                        Alert.alert(nextErrorMessage)
                                    })
                                },
                            },
                        ],
                    )
                    return
                }
            }

            const errorMessage = error instanceof ApiError && error.message
                ? error.message
                : t("cart.checkoutFailed")
            Alert.alert(errorMessage)
        } finally {
            setIsOpeningCheckout(false)
        }
    }

    const handleConfirmOpenCheckout = () => {
        Alert.alert(
            t("cart.checkoutDraftNoticeTitle"),
            t("cart.checkoutDraftNoticeMessage"),
            [
                {
                    text: t("common.cancel"),
                    style: "cancel",
                },
                {
                    text: t("cart.checkoutDraftNoticeContinue"),
                    onPress: () => {
                        void handleOpenCheckout()
                    },
                },
            ],
        )
    }

    if (variant === "product") {
        if (selectedBasketItem) {
            return (
                <View style={stickyFooterStyles.quantityControl}>
                    <Pressable
                        accessibilityLabel={t("cart.decreaseQuantity")}
                        accessibilityRole="button"
                        disabled={updating}
                        onPress={() => {
                            void handleDecreaseBasketQuantity()
                        }}
                        style={({ pressed }) => [
                            stickyFooterStyles.quantityButton,
                            updating && stickyFooterStyles.quantityButtonDisabled,
                            pressed && stickyFooterStyles.quantityButtonPressed,
                        ]}
                    >
                        <Text style={stickyFooterStyles.quantityButtonText}>-</Text>
                    </Pressable>

                    <View style={stickyFooterStyles.quantityValueWrap}>
                        <Text style={stickyFooterStyles.quantityValue}>{selectedBasketItem.quantity}</Text>
                    </View>

                    <Pressable
                        accessibilityLabel={t("cart.increaseQuantity")}
                        accessibilityRole="button"
                        disabled={!canIncreaseSelectedVariant}
                        onPress={() => {
                            void handleIncreaseBasketQuantity()
                        }}
                        style={({ pressed }) => [
                            stickyFooterStyles.quantityButton,
                            !canIncreaseSelectedVariant && stickyFooterStyles.quantityButtonDisabled,
                            pressed && stickyFooterStyles.quantityButtonPressed,
                        ]}
                    >
                        <Text style={stickyFooterStyles.quantityButtonText}>+</Text>
                    </Pressable>
                </View>
            )
        }

        return (
            <Pressable
                accessibilityLabel={t("product.chooseDosagesCta")}
                accessibilityRole="button"
                disabled={isProductActionDisabled}
                onPress={() => {
                    void handleAddToBasketPress()
                }}
                style={({ pressed }) => [
                    stickyFooterStyles.actionButton,
                    isProductActionDisabled && stickyFooterStyles.actionButtonDisabled,
                    pressed && stickyFooterStyles.actionButtonPressed,
                ]}
            >
                <Text style={stickyFooterStyles.actionButtonText}>{t("product.chooseDosagesCta")}</Text>
            </Pressable>
        )
    }

    const basketActionLabel = t("cart.checkoutCta")

    return (
        <Pressable
            accessibilityLabel={basketActionLabel}
            accessibilityRole="button"
            disabled={isOpeningCheckout}
            onPress={() => {
                handleConfirmOpenCheckout()
            }}
            style={({ pressed }) => [
                stickyFooterStyles.actionButton,
                isOpeningCheckout && stickyFooterStyles.actionButtonDisabled,
                pressed && stickyFooterStyles.actionButtonPressed,
            ]}
        >
            <Text style={stickyFooterStyles.actionButtonText}>{basketActionLabel}</Text>
        </Pressable>
    )
}
