import { useEffect } from "react"

import { getBasketSnapshot, setBasketSnapshot, subscribeBasketSnapshot } from "@/hooks/basket/basket-store"
import type { UseBasketResult } from "@/hooks/basket/use-basket.types"
import { useAsyncData } from "@/hooks/shared/use-async-data"
import { useAuth } from "@/providers/auth-provider.context"
import { getBasket } from "@/services/api/basket"
import { getGuestBasket } from "@/services/guest-cart"
import type { BasketRead } from "@/types/basket"
import { commerceAccountRevision } from "@/services/commerce-account"

let basketLoadRequest: { revision: number; promise: Promise<BasketRead> } | null = null

async function loadBasketSnapshot(isAuthenticated: boolean) {
    const revision = commerceAccountRevision()
    if (!basketLoadRequest || basketLoadRequest.revision !== revision) {
        const promise = (isAuthenticated ? getBasket() : getGuestBasket())
            .then((nextBasket) => {
                if (commerceAccountRevision() === revision) setBasketSnapshot(nextBasket)
                return nextBasket
            })
            .finally(() => {
                if (basketLoadRequest?.revision === revision) basketLoadRequest = null
            })
        basketLoadRequest = { revision, promise }
    }

    return basketLoadRequest.promise
}

export function useBasket(): UseBasketResult {
    const { isAuthenticated, isReady, user } = useAuth()
    const { data: basket, error, loading, reload, setData } = useAsyncData({
        deps: [user?.id ?? null],
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
