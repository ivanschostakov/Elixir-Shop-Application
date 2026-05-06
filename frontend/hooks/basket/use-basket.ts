import { useEffect } from "react"

import { getBasketSnapshot, setBasketSnapshot, subscribeBasketSnapshot } from "@/hooks/basket/basket-store"
import type { UseBasketResult } from "@/hooks/basket/use-basket.types"
import { useAsyncData } from "@/hooks/shared/use-async-data"
import { useAuth } from "@/providers/auth-provider.context"
import { getBasket } from "@/services/api/basket"
import type { BasketRead } from "@/types/basket"

let basketLoadRequest: Promise<BasketRead> | null = null

async function loadBasketSnapshot() {
    if (!basketLoadRequest) {
        basketLoadRequest = getBasket()
            .then((nextBasket) => {
                setBasketSnapshot(nextBasket)
                return nextBasket
            })
            .finally(() => {
                basketLoadRequest = null
            })
    }

    return basketLoadRequest
}

export function useBasket(): UseBasketResult {
    const { isAuthenticated, isReady } = useAuth()
    const { data: basket, error, loading, reload, setData } = useAsyncData({
        deps: [isAuthenticated],
        enabled: isReady && isAuthenticated,
        fetcher: loadBasketSnapshot,
        initialData: getBasketSnapshot(),
    })

    useEffect(() => subscribeBasketSnapshot(setData), [setData])

    useEffect(() => {
        if (isReady && !isAuthenticated) {
            setData(null)
        }
    }, [isAuthenticated, isReady, setData])

    return {
        basket,
        error,
        loading,
        reload,
    }
}
