import type { BasketRead } from "@/types/basket"
import { clearBasketDraftEditingId } from "@/hooks/basket/basket-draft-editing-store"

type BasketListener = (basket: BasketRead | null) => void

let basketSnapshot: BasketRead | null = null

const listeners = new Set<BasketListener>()

export function getBasketSnapshot() {
    return basketSnapshot
}

export function setBasketSnapshot(nextBasket: BasketRead | null) {
    basketSnapshot = nextBasket

    if (!nextBasket || nextBasket.total_quantity === 0 || nextBasket.items.length === 0) {
        clearBasketDraftEditingId()
    }

    listeners.forEach((listener) => listener(nextBasket))
}

export function clearBasketSnapshot() {
    if (!basketSnapshot) {
        setBasketSnapshot(null)
        return
    }

    setBasketSnapshot({
        ...basketSnapshot,
        items: [],
        items_count: 0,
        total_quantity: 0,
        total_amount: "0.00",
        has_unavailable_items: false,
    })
}

export function subscribeBasketSnapshot(listener: BasketListener) {
    listeners.add(listener)

    return () => {
        listeners.delete(listener)
    }
}
