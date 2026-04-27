import { useState } from "react"

import {
    addFavouriteProduct,
    getFavouriteProductStatus,
    removeFavouriteProduct,
} from "@/services/api/favourites"
import { useAsyncData } from "@/hooks/shared/use-async-data"
import type { UseProductFavouriteResult } from "@/hooks/products/use-product-favourite.types"
import { getErrorMessage } from "@/utils/errors"

export function useProductFavourite(productId: number): UseProductFavouriteResult {
    const [updating, setUpdating] = useState(false)
    const [actionError, setActionError] = useState<string | null>(null)
    const {
        data: isFavourite,
        error: loadError,
        loading,
        setData: setIsFavourite,
    } = useAsyncData({
        deps: [productId],
        fetcher: async () => {
            if (!productId || !Number.isFinite(productId)) {
                throw new Error("Invalid product id")
            }

            const data = await getFavouriteProductStatus(productId)
            return data.is_favoured
        },
        initialData: false,
        resetOnLoad: true,
    })

    const toggleFavourite = async () => {
        if (!productId || !Number.isFinite(productId)) {
            const nextError = "Invalid product id"
            setActionError(nextError)
            throw new Error(nextError)
        }

        setUpdating(true)
        setActionError(null)

        try {
            if (isFavourite) {
                await removeFavouriteProduct(productId)
                setIsFavourite(false)
                return false
            }

            await addFavouriteProduct(productId)
            setIsFavourite(true)
            return true
        } catch (err) {
            const nextError = getErrorMessage(err)
            setActionError(nextError)
            throw err instanceof Error ? err : new Error(nextError)
        } finally {
            setUpdating(false)
        }
    }

    return {
        error: actionError ?? loadError,
        isFavourite,
        loading,
        toggleFavourite,
        updating,
    }
}
