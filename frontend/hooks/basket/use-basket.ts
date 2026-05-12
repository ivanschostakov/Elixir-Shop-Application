import { useEffect } from "react"

import { getBasketSnapshot, setBasketSnapshot, subscribeBasketSnapshot } from "@/hooks/basket/basket-store"
import type { UseBasketResult } from "@/hooks/basket/use-basket.types"
import { useAsyncData } from "@/hooks/shared/use-async-data"
import { useAuth } from "@/providers/auth-provider.context"
import { getBasket } from "@/services/api/basket"
import { getGuestBasket } from "@/services/guest-cart"
import type { BasketRead } from "@/types/basket"

let basketLoadRequest: { isAuthenticated: boolean; promise: Promise<BasketRead> } | null = null

async function loadBasketSnapshot(isAuthenticated: boolean) {
    if (!basketLoadRequest || basketLoadRequest.isAuthenticated !== isAuthenticated) {
        const promise = (isAuthenticated ? getBasket() : getGuestBasket())
            .then((nextBasket) => {
                setBasketSnapshot(nextBasket)
                return nextBasket
            })
            .finally(() => {
                basketLoadRequest = null
            })
        basketLoadRequest = { isAuthenticated, promise }
    }

    return basketLoadRequest.promise
}

export function useBasket(): UseBasketResult {
    const { isAuthenticated, isReady } = useAuth()
    const { data: basket, error, loading, reload, setData } = useAsyncData({
        deps: [isAuthenticated],
        enabled: isReady,
        fetcher: () => loadBasketSnapshot(isAuthenticated),
        initialData: getBasketSnapshot(),
    })

    useEffect(() => subscribeBasketSnapshot(setData), [setData])

    return {
        basket,
        error,
        loading,
        reload,
    }
}
