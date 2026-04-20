import { useSyncExternalStore } from "react"

import type { RememberedProductVariantSelection } from "@/hooks/products/product-variant-selection-store.types"

const productVariantSelectionMemory = new Map<number, RememberedProductVariantSelection>()
const listeners = new Set<() => void>()

function notifyListeners() {
    listeners.forEach((listener) => {
        listener()
    })
}

function subscribeProductVariantSelectionStore(listener: () => void) {
    listeners.add(listener)

    return () => {
        listeners.delete(listener)
    }
}

export function getRememberedProductVariantSelection(productId: number) {
    return productVariantSelectionMemory.get(productId) ?? null
}

export function setRememberedProductVariantSelection(
    productId: number,
    selection: RememberedProductVariantSelection | null,
) {
    if (selection) {
        productVariantSelectionMemory.set(productId, selection)
    } else {
        productVariantSelectionMemory.delete(productId)
    }

    notifyListeners()
}

export function useRememberedProductVariantSelection(productId: number | null) {
    return useSyncExternalStore(
        subscribeProductVariantSelectionStore,
        () => {
            if (productId === null || !Number.isFinite(productId)) {
                return null
            }

            return getRememberedProductVariantSelection(productId)
        },
        () => null,
    )
}
