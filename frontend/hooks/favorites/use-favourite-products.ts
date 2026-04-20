import { useEffect, useRef, useState } from "react"
import { useIsFocused } from "@react-navigation/native"

import {
    getFavouriteProducts,
    removeFavouriteProduct,
} from "@/services/api/favourites"
import type { UseFavouriteProductsResult } from "@/hooks/favorites/use-favourite-products.types"
import { useAsyncData } from "@/hooks/shared/use-async-data"

export function useFavouriteProducts(): UseFavouriteProductsResult {
    const [refreshing, setRefreshing] = useState(false)
    const [removingProductId, setRemovingProductId] = useState<number | null>(null)
    const isFocused = useIsFocused()
    const hasLoadedOnceRef = useRef(false)
    const {
        data: products,
        error,
        loading,
        reload,
        setData: setProducts,
    } = useAsyncData({
        deps: [],
        enabled: false,
        fetcher: getFavouriteProducts,
        initialData: [],
    })

    const refresh = async () => {
        setRefreshing(true)

        try {
            await reload({ showLoading: false })
        } finally {
            setRefreshing(false)
            hasLoadedOnceRef.current = true
        }
    }

    useEffect(() => {
        if (!isFocused) {
            return
        }

        void reload({ showLoading: !hasLoadedOnceRef.current }).finally(() => {
            hasLoadedOnceRef.current = true
        })
    }, [isFocused, reload])

    const removeFavourite = async (productId: number) => {
        if (!productId || !Number.isFinite(productId)) {
            throw new Error("Invalid product id")
        }

        setRemovingProductId(productId)

        try {
            await removeFavouriteProduct(productId)
            setProducts((currentProducts) =>
                currentProducts.filter((product) => product.id !== productId)
            )
        } catch (err) {
            throw err instanceof Error ? err : new Error("Unknown error")
        } finally {
            setRemovingProductId((currentProductId) =>
                currentProductId === productId ? null : currentProductId
            )
        }
    }

    return {
        error,
        loading,
        products,
        refresh,
        refreshing,
        removingProductId,
        removeFavourite,
    }
}
