import { useCallback, useMemo, useState } from "react"

import { setBasketDraftEditingId } from "@/hooks/basket/basket-draft-editing-store"
import { setBasketSnapshot } from "@/hooks/basket/basket-store"
import type { UseBasketMutationsResult } from "@/hooks/basket/use-basket.types"
import { addBasketItem, clearBasket, removeBasketItem, restoreDraftToBasket, updateBasketItem } from "@/services/api/basket"
import type { BasketRead } from "@/types/basket"
import { getErrorMessage, showBackendErrorAlert } from "@/utils/errors"

function assertPositiveInteger(value: number, label: string) {
    if (!Number.isInteger(value) || value < 1) {
        throw new Error(`Invalid ${label}`)
    }
}

export function useBasketMutations(): UseBasketMutationsResult {
    const [updating, setUpdating] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const runMutation = useCallback(async (mutation: () => Promise<BasketRead>) => {
        setUpdating(true)
        setError(null)

        try {
            const nextBasket = await mutation()
            setBasketSnapshot(nextBasket)
            return nextBasket
        } catch (mutationError) {
            const nextError = getErrorMessage(mutationError)
            setError(nextError)
            showBackendErrorAlert(mutationError, nextError)
            throw mutationError instanceof Error ? mutationError : new Error(nextError)
        } finally {
            setUpdating(false)
        }
    }, [])

    const addItem = useCallback((variantId: number, quantity = 1) => {
        assertPositiveInteger(variantId, "variant id")
        assertPositiveInteger(quantity, "quantity")

        return runMutation(() =>
            addBasketItem({
                quantity,
                variant_id: variantId,
            })
        )
    }, [runMutation])

    const updateItemQuantity = useCallback((itemId: number, quantity: number) => {
        assertPositiveInteger(itemId, "item id")
        assertPositiveInteger(quantity, "quantity")

        return runMutation(() =>
            updateBasketItem(itemId, {
                quantity,
            })
        )
    }, [runMutation])

    const removeItem = useCallback((itemId: number) => {
        assertPositiveInteger(itemId, "item id")
        return runMutation(() => removeBasketItem(itemId))
    }, [runMutation])

    const clear = useCallback(() => runMutation(() => clearBasket()), [runMutation])

    const restoreDraft = useCallback(async (draftId: number) => {
        assertPositiveInteger(draftId, "draft id")

        const nextBasket = await runMutation(() => restoreDraftToBasket(draftId))
        setBasketDraftEditingId(draftId)
        return nextBasket
    }, [runMutation])

    return useMemo(
        () => ({
            updating,
            error,
            addItem,
            updateItemQuantity,
            removeItem,
            clear,
            restoreDraft,
        }),
        [addItem, clear, error, removeItem, restoreDraft, updateItemQuantity, updating],
    )
}
