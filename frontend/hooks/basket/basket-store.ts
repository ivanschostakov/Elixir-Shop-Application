import type { BasketRead } from "@/types/basket"

type BasketListener = (basket: BasketRead | null) => void

let basketSnapshot: BasketRead | null = null

const listeners = new Set<BasketListener>()

export function getBasketSnapshot() {
    return basketSnapshot
}

export function setBasketSnapshot(nextBasket: BasketRead | null) {
    basketSnapshot = nextBasket
    listeners.forEach((listener) => listener(nextBasket))
}

export function subscribeBasketSnapshot(listener: BasketListener) {
    listeners.add(listener)

    return () => {
        listeners.delete(listener)
    }
}
