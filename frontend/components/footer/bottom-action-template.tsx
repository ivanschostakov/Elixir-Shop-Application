import { Alert, Pressable, Text, View } from "react-native"
import { usePathname, useRouter } from "expo-router"

import { stickyFooterStyles } from "@/components/footer/sticky-footer.styles"
import { getAddToCartErrorMessage } from "@/components/footer/sticky-footer.utils"
import { ROUTES, getProductIdFromRoute, isProductRoute } from "@/constants/routes"
import { useBasket } from "@/hooks/basket/use-basket"
import { useBasketMutations } from "@/hooks/basket/use-basket-mutations"
import { requestDeliveryCountryPickerFocus } from "@/hooks/delivery/delivery-country-picker-focus-store"
import { useSelectedDeliveryCountry } from "@/hooks/delivery/delivery-country-selection-store"
import { useRememberedProductVariantSelection } from "@/hooks/products/product-variant-selection-store"
import { useLanguage } from "@/providers/language-provider"

type BottomActionTemplateProps = {
    variant: "basket" | "product"
}

export function BottomActionTemplate({ variant }: BottomActionTemplateProps) {
    const pathname = usePathname()
    const router = useRouter()
    const { t } = useLanguage()
    const { basket } = useBasket()
    const { addItem, error: basketError, removeItem, updateItemQuantity, updating } = useBasketMutations()
    const selectedDeliveryCountry = useSelectedDeliveryCountry()
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

    const basketActionLabel = selectedDeliveryCountry
        ? t("cart.deliveryCta")
        : t("cart.pickDeliveryCountryCta")

    return (
        <Pressable
            accessibilityLabel={basketActionLabel}
            accessibilityRole="button"
            onPress={() => {
                if (selectedDeliveryCountry) {
                    router.push(ROUTES.delivery)
                    return
                }

                requestDeliveryCountryPickerFocus()
            }}
            style={({ pressed }) => [
                stickyFooterStyles.actionButton,
                pressed && stickyFooterStyles.actionButtonPressed,
            ]}
        >
            <Text style={stickyFooterStyles.actionButtonText}>{basketActionLabel}</Text>
        </Pressable>
    )
}
