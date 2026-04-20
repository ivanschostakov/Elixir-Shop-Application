import type { Animated } from "react-native"
import type Swipeable from "react-native-gesture-handler/Swipeable"

import type { BasketItemRead } from "@/types/basket"

export type SwipeDeleteActionProps = {
    disabled: boolean
    dragX: Animated.AnimatedInterpolation<number>
    isArmed: boolean
    label: string
    onDragProgress: (value: number) => void
    onPress: () => void
}

export type CartBasketItemProps = {
    item: BasketItemRead
    onConfirmRemove: (itemId: number) => void
    onDecrease: (item: BasketItemRead) => void
    onIncrease: (item: BasketItemRead) => void
    onOpenProduct: (productId: number) => void
    swipeableRef: (instance: Swipeable | null) => void
    updating: boolean
}
