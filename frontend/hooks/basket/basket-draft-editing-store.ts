import { useSyncExternalStore } from "react"

let basketDraftEditingId: number | null = null

const listeners = new Set<() => void>()

function notifyListeners() {
    listeners.forEach((listener) => {
        listener()
    })
}

function subscribeBasketDraftEditingStore(listener: () => void) {
    listeners.add(listener)

    return () => {
        listeners.delete(listener)
    }
}

function getBasketDraftEditingIdSnapshot() {
    return basketDraftEditingId
}

export function setBasketDraftEditingId(nextDraftId: number | null) {
    if (basketDraftEditingId === nextDraftId) {
        return
    }

    basketDraftEditingId = nextDraftId
    notifyListeners()
}

export function clearBasketDraftEditingId() {
    setBasketDraftEditingId(null)
}

export function useBasketDraftEditingId() {
    return useSyncExternalStore(
        subscribeBasketDraftEditingStore,
        getBasketDraftEditingIdSnapshot,
        () => null,
    )
}
