import { useCallback, useEffect, useRef, useState } from "react"
import {
    Alert,
    Image,
    Platform,
    Pressable,
    Text,
    View,
} from "react-native"
import Swipeable from "react-native-gesture-handler/Swipeable"

import { SavedIcon } from "@/components/footer/sticky-footer.icons"
import { formatProductPrice } from "@/components/content/product-content"
import { useProductFavourite } from "@/hooks/products/use-product-favourite"
import { useLanguage } from "@/providers/language-provider"
import { FULL_SWIPE_REMOVE_TRIGGER } from "@/screens/cart/cart-screen.constants"
import { cartScreenStyles } from "@/screens/cart/cart-screen.styles"
import type {
    CartBasketItemProps,
    SwipeDeleteActionProps,
} from "@/screens/cart/cart-basket-item.types"
import { colors } from "@/theme/colors"
import { showRemoveFavouriteConfirmation } from "@/utils/favorites/show-remove-favourite-confirmation"

function SwipeDeleteAction({
    disabled,
    dragX,
    isArmed,
    label,
    onDragProgress,
    onPress,
}: SwipeDeleteActionProps) {
    useEffect(() => {
        const listenerId = dragX.addListener(({ value }) => {
            onDragProgress(value)
        })

        return () => {
            dragX.removeListener(listenerId)
        }
    }, [dragX, onDragProgress])

    return (
        <Pressable
            accessibilityLabel={label}
            accessibilityRole="button"
            disabled={disabled}
            onPress={onPress}
            style={({ pressed }) => [
                cartScreenStyles.swipeAction,
                isArmed && cartScreenStyles.swipeActionArmed,
                disabled && cartScreenStyles.actionDisabled,
                pressed && cartScreenStyles.pressed,
            ]}
        >
            <Text
                style={[
                    cartScreenStyles.swipeActionText,
                    isArmed && cartScreenStyles.swipeActionTextArmed,
                ]}
            >
                {label}
            </Text>
        </Pressable>
    )
}

export function CartBasketItem({
    item,
    onConfirmRemove,
    onDecrease,
    onIncrease,
    onOpenProduct,
    swipeableRef,
    updating,
}: CartBasketItemProps) {
    const { t } = useLanguage()
    const rowSwipeableRef = useRef<Swipeable | null>(null)
    const fullSwipeTriggeredRef = useRef(false)
    const [isFullSwipeArmed, setIsFullSwipeArmed] = useState(false)
    const {
        error: favouriteError,
        isFavourite,
        loading: favouriteLoading,
        toggleFavourite,
        updating: favouriteUpdating,
    } = useProductFavourite(item.product.id)

    const itemImageUrl = item.variant.image_url || item.product.image_url
    const lineTotalLabel = formatProductPrice(item.line_total) ?? "—"
    const unitPriceLabel = formatProductPrice(item.unit_price) ?? "—"
    const availabilityLabel = !item.is_available
        ? item.available_quantity === 0
            ? t("product.variantOutOfStock")
            : `${t("cart.availablePrefix")} ${item.available_quantity}`
        : null

    const isBusy = updating || favouriteLoading || favouriteUpdating

    const handleToggleFavourite = async () => {
        try {
            const nextIsFavourite = await toggleFavourite()
            Alert.alert(nextIsFavourite ? t("product.favoriteAdded") : t("product.favoriteRemoved"))
        } catch (error) {
            Alert.alert(
                error instanceof Error
                    ? error.message
                    : favouriteError ?? t("product.favoriteUpdateFailed"),
            )
        }
    }

    const handleFavouritePress = () => {
        if (!isFavourite) {
            void handleToggleFavourite()
            return
        }

        showRemoveFavouriteConfirmation(t, () => {
            void handleToggleFavourite()
        })
    }

    const resetFullSwipeState = useCallback(() => {
        fullSwipeTriggeredRef.current = false
        setIsFullSwipeArmed(false)
    }, [])

    const handleFullSwipeProgress = useCallback((value: number) => {
        if (value <= -FULL_SWIPE_REMOVE_TRIGGER && !fullSwipeTriggeredRef.current) {
            fullSwipeTriggeredRef.current = true
            setIsFullSwipeArmed(true)
        }
    }, [])

    const handleDeleteActionPress = () => {
        rowSwipeableRef.current?.close()
        resetFullSwipeState()
        onConfirmRemove(item.id)
    }

    const rowContent = (
        <View
            style={[
                cartScreenStyles.itemCard,
                !item.is_available && cartScreenStyles.itemCardUnavailable,
            ]}
        >
            <View style={cartScreenStyles.itemMediaColumn}>
                <Pressable
                    accessibilityLabel={item.product.name}
                    accessibilityRole="button"
                    onPress={() => {
                        onOpenProduct(item.product.id)
                    }}
                    style={({ pressed }) => [
                        cartScreenStyles.itemImageButton,
                        pressed && cartScreenStyles.pressed,
                    ]}
                >
                    <Image
                        source={{ uri: itemImageUrl }}
                        style={cartScreenStyles.itemImage}
                        resizeMode="cover"
                    />
                </Pressable>
            </View>

            <View style={cartScreenStyles.itemContent}>
                <Pressable
                    accessibilityLabel={item.product.name}
                    accessibilityRole="button"
                    onPress={() => {
                        onOpenProduct(item.product.id)
                    }}
                    style={({ pressed }) => [
                        cartScreenStyles.itemDetailsButton,
                        pressed && cartScreenStyles.pressed,
                    ]}
                >
                    <View style={cartScreenStyles.priceStack}>
                        <Text style={cartScreenStyles.itemLineTotal}>{lineTotalLabel}</Text>
                        <Text style={cartScreenStyles.itemUnitPrice}>{`${unitPriceLabel}/ед`}</Text>
                    </View>

                    <View style={cartScreenStyles.itemCopy}>
                        <Text numberOfLines={3} style={cartScreenStyles.itemTitle}>
                            {item.product.name}
                        </Text>
                        <Text numberOfLines={1} style={cartScreenStyles.itemVariant}>
                            {item.variant.name}
                        </Text>
                        <Text numberOfLines={1} style={cartScreenStyles.itemSku}>
                            {item.variant.sku ?? item.product.sku}
                        </Text>
                        {availabilityLabel ? (
                            <Text style={cartScreenStyles.itemAvailability}>{availabilityLabel}</Text>
                        ) : null}
                    </View>
                </Pressable>

                <View style={cartScreenStyles.itemControlRow}>
                    <Pressable
                        accessibilityLabel={isFavourite ? t("product.favoriteRemoved") : t("product.favoriteAdded")}
                        accessibilityRole="button"
                        disabled={isBusy}
                        onPress={handleFavouritePress}
                        style={({ pressed }) => [
                            cartScreenStyles.iconActionButton,
                            isBusy && cartScreenStyles.actionDisabled,
                            pressed && cartScreenStyles.pressed,
                        ]}
                    >
                        <SavedIcon color={isFavourite ? colors.favorite : colors.mutedText} />
                    </Pressable>

                    <View style={cartScreenStyles.quantityControl}>
                        <Pressable
                            accessibilityLabel={t("cart.decreaseQuantity")}
                            accessibilityRole="button"
                            disabled={updating}
                            onPress={() => {
                                onDecrease(item)
                            }}
                            style={({ pressed }) => [
                                cartScreenStyles.quantityButton,
                                updating && cartScreenStyles.actionDisabled,
                                pressed && cartScreenStyles.pressed,
                            ]}
                        >
                            <Text style={cartScreenStyles.quantityButtonText}>−</Text>
                        </Pressable>

                        <Text style={cartScreenStyles.quantityValue}>{item.quantity}</Text>

                        <Pressable
                            accessibilityLabel={t("cart.increaseQuantity")}
                            accessibilityRole="button"
                            disabled={updating || item.quantity >= item.available_quantity}
                            onPress={() => {
                                onIncrease(item)
                            }}
                            style={({ pressed }) => [
                                cartScreenStyles.quantityButton,
                                (updating || item.quantity >= item.available_quantity) &&
                                    cartScreenStyles.actionDisabled,
                                pressed && cartScreenStyles.pressed,
                            ]}
                        >
                            <Text style={cartScreenStyles.quantityButtonText}>+</Text>
                        </Pressable>
                    </View>

                    {Platform.OS === "web" ? (
                        <Pressable
                            accessibilityLabel={t("cart.removeItem")}
                            accessibilityRole="button"
                            disabled={updating}
                            onPress={handleDeleteActionPress}
                            style={({ pressed }) => [
                                cartScreenStyles.inlineRemoveButton,
                                updating && cartScreenStyles.actionDisabled,
                                pressed && cartScreenStyles.pressed,
                            ]}
                        >
                            <Text style={cartScreenStyles.inlineRemoveButtonText}>
                                {t("cart.removeItem")}
                            </Text>
                        </Pressable>
                    ) : null}
                </View>
            </View>
        </View>
    )

    if (Platform.OS === "web") {
        swipeableRef(null)
        return rowContent
    }

    return (
        <Swipeable
            friction={2}
            onSwipeableClose={resetFullSwipeState}
            onSwipeableOpen={(direction) => {
                if (direction !== "left" || !fullSwipeTriggeredRef.current) {
                    return
                }

                handleDeleteActionPress()
            }}
            overshootFriction={8}
            overshootRight
            ref={(instance) => {
                rowSwipeableRef.current = instance
                swipeableRef(instance)
            }}
            renderRightActions={(_, dragX) => (
                <SwipeDeleteAction
                    disabled={updating}
                    dragX={dragX}
                    isArmed={isFullSwipeArmed}
                    label={t("cart.removeItem")}
                    onDragProgress={handleFullSwipeProgress}
                    onPress={handleDeleteActionPress}
                />
            )}
            rightThreshold={46}
        >
            {rowContent}
        </Swipeable>
    )
}
