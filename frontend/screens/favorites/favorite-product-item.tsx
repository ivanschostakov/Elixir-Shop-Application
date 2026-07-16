import { useCallback, useEffect, useRef, useState } from "react"
import {
    Platform,
    Pressable,
    Text,
    View,
    type Animated,
} from "react-native"
import Swipeable from "react-native-gesture-handler/Swipeable"

import { ListCard } from "@/components/content/list-card"
import { SavedIcon } from "@/components/footer/sticky-footer.icons"
import { useLanguage } from "@/providers/language-provider"
import { SwipeDeleteActionProps } from "@/screens/cart/cart-basket-item.types"
import { FULL_SWIPE_REMOVE_TRIGGER } from "@/screens/cart/cart-screen.constants"
import { createCartScreenStyles } from "@/screens/cart/cart-screen.styles"
import { createFavoritesScreenStyles } from "@/screens/favorites/favorites-screen.styles"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useTheme } from "@/providers/theme-provider"
import type { FavoriteProductItemProps } from "@/screens/favorites/favorite-product-item.types"

function FavoriteSwipeAction({
    disabled,
    dragX,
    isArmed,
    label,
    onDragProgress,
    onPress,
}: SwipeDeleteActionProps) {
    const cartScreenStyles = useThemeStyles(createCartScreenStyles)
    const favoritesScreenStyles = useThemeStyles(createFavoritesScreenStyles)
    useEffect(() => {
        const listenerId = dragX.addListener(({ value }) => {
            onDragProgress(value)
        })

        return () => {
            dragX.removeListener(listenerId)
        }
    }, [dragX, onDragProgress])

    return (
        <View style={favoritesScreenStyles.swipeActionContainer}>
            <Pressable
                accessibilityLabel={label}
                accessibilityRole="button"
                disabled={disabled}
                onPress={onPress}
                style={({ pressed }) => [
                    cartScreenStyles.swipeAction,
                    favoritesScreenStyles.swipeAction,
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
        </View>
    )
}

export function FavoriteProductItem({ isRemoving, onRemove, product }: FavoriteProductItemProps) {
    const favoritesScreenStyles = useThemeStyles(createFavoritesScreenStyles)
    const { palette } = useTheme()
    const { t } = useLanguage()
    const rowSwipeableRef = useRef<Swipeable | null>(null)
    const fullSwipeTriggeredRef = useRef(false)
    const [isFullSwipeArmed, setIsFullSwipeArmed] = useState(false)
    const removeLabel = t("cart.removeItem")

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

    const handleRemovePress = () => {
        rowSwipeableRef.current?.close()
        resetFullSwipeState()
        void onRemove(product.id)
    }

    const action = (
        <Pressable
            accessibilityLabel={removeLabel}
            accessibilityRole="button"
            disabled={isRemoving}
            onPress={handleRemovePress}
            style={({ pressed }) => [
                favoritesScreenStyles.bookmarkButton,
                pressed && favoritesScreenStyles.bookmarkButtonPressed,
                isRemoving && favoritesScreenStyles.bookmarkButtonDisabled,
            ]}
        >
            <SavedIcon color={palette.favorite} />
        </Pressable>
    )

    const rowContent = <ListCard action={action} product={product} />

    if (Platform.OS === "web") {
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

                handleRemovePress()
            }}
            overshootFriction={8}
            overshootRight
            ref={(instance) => {
                rowSwipeableRef.current = instance
            }}
            renderRightActions={(_, dragX: Animated.AnimatedInterpolation<number>) => (
                <FavoriteSwipeAction
                    disabled={isRemoving}
                    dragX={dragX}
                    isArmed={isFullSwipeArmed}
                    label={removeLabel}
                    onDragProgress={handleFullSwipeProgress}
                    onPress={handleRemovePress}
                />
            )}
            rightThreshold={46}
        >
            {rowContent}
        </Swipeable>
    )
}
