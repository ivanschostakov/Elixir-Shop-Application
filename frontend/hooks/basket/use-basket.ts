import { useEffect } from "react"

import { getBasketSnapshot, setBasketSnapshot, subscribeBasketSnapshot } from "@/hooks/basket/basket-store"
import type { UseBasketResult } from "@/hooks/basket/use-basket.types"
import { useAsyncData } from "@/hooks/shared/use-async-data"
import { getBasket } from "@/services/api/basket"

export function useBasket(): UseBasketResult {
    const { data: basket, error, loading, reload, setData } = useAsyncData({
        deps: [],
        fetcher: async () => {
            const nextBasket = await getBasket()
            setBasketSnapshot(nextBasket)
            return nextBasket
        },
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
