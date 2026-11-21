import type { BasketRead } from "@/types/basket"
import { clearBasketDraftEditingId } from "@/hooks/basket/basket-draft-editing-store"
import { commerceAccountId, subscribeCommerceAccount } from "@/services/commerce-account"

type BasketListener = (basket: BasketRead | null) => void

let basketSnapshot: BasketRead | null = null

const listeners = new Set<BasketListener>()

export function getBasketSnapshot() {
    return basketSnapshot
}

export function setBasketSnapshot(nextBasket: BasketRead | null) {
    if (nextBasket && nextBasket.user_id !== (commerceAccountId() ?? 0)) return
    basketSnapshot = nextBasket

    if (!nextBasket || nextBasket.total_quantity === 0 || nextBasket.items.length === 0) {
        clearBasketDraftEditingId()
    }

    listeners.forEach((listener) => listener(nextBasket))
}

export function clearBasketSnapshot() {
    setBasketSnapshot(null)
}

subscribeCommerceAccount(clearBasketSnapshot)

export function subscribeBasketSnapshot(listener: BasketListener) {
    listeners.add(listener)

    return () => {
        listeners.delete(listener)
    }
}
