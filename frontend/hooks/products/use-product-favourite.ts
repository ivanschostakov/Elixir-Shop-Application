import { useState } from "react"
import { router } from "expo-router"

import { ROUTES } from "@/constants/routes"
import { showAuthRequiredAlert } from "@/components/navigation/auth-required-alert"
import {
    addFavouriteProduct,
    getFavouriteProductStatus,
    removeFavouriteProduct,
} from "@/services/api/favourites"
import { useAsyncData } from "@/hooks/shared/use-async-data"
import type { UseProductFavouriteResult } from "@/hooks/products/use-product-favourite.types"
import { useAuth } from "@/providers/auth-provider"
import { getErrorMessage, showBackendErrorAlert } from "@/utils/errors"

export const AUTH_REQUIRED_PROMPTED_ERROR = "AUTH_REQUIRED_PROMPTED"

export function useProductFavourite(productId: number): UseProductFavouriteResult {
    const { isAuthenticated } = useAuth()
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
        enabled: isAuthenticated,
        initialData: false,
        resetOnLoad: true,
    })

    const toggleFavourite = async () => {
        if (!isAuthenticated) {
            showAuthRequiredAlert({
                onLogin: () => {
                    router.push(ROUTES.login)
                },
            })
            throw new Error(AUTH_REQUIRED_PROMPTED_ERROR)
        }

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
            showBackendErrorAlert(err, nextError)
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
