import { router } from "expo-router"
import { useState } from "react"

import { showAuthRequiredAlert } from "@/components/navigation/auth-required-alert"
import { ROUTES } from "@/constants/routes"
import { useAsyncData } from "@/hooks/shared/use-async-data"
import { useAuth } from "@/providers/auth-provider"
import {
    getProductStockSubscriptionStatus,
    subscribeToProductStock,
} from "@/services/api/stock-subscriptions"
import { getErrorMessage } from "@/utils/errors"

export const STOCK_SUBSCRIPTION_AUTH_REQUIRED_PROMPTED_ERROR =
    "STOCK_SUBSCRIPTION_AUTH_REQUIRED_PROMPTED"

export function useProductStockSubscription(
    productId: number | null,
    enabled: boolean,
) {
    const { isAuthenticated } = useAuth()
    const [updating, setUpdating] = useState(false)
    const [actionError, setActionError] = useState<string | null>(null)
    const {
        data: isSubscribed,
        error: loadError,
        loading,
        setData: setIsSubscribed,
    } = useAsyncData({
        deps: [productId],
        enabled: enabled && isAuthenticated && productId !== null,
        fetcher: async () => {
            if (productId === null || !Number.isFinite(productId)) {
                throw new Error("Invalid product id")
            }
            const status = await getProductStockSubscriptionStatus(productId)
            return status.is_subscribed
        },
        initialData: false,
        resetOnLoad: true,
    })

    const subscribe = async () => {
        if (!isAuthenticated) {
            showAuthRequiredAlert({
                onLogin: () => {
                    router.push(ROUTES.login)
                },
            })
            throw new Error(STOCK_SUBSCRIPTION_AUTH_REQUIRED_PROMPTED_ERROR)
        }

        if (productId === null || !Number.isFinite(productId)) {
            const nextError = "Invalid product id"
            setActionError(nextError)
            throw new Error(nextError)
        }

        setUpdating(true)
        setActionError(null)
        try {
            const status = await subscribeToProductStock(productId)
            setIsSubscribed(status.is_subscribed)
            return status.is_subscribed
        } catch (error) {
            setActionError(getErrorMessage(error))
            throw error
        } finally {
            setUpdating(false)
        }
    }

    return {
        error: actionError ?? loadError,
        isSubscribed,
        loading,
        subscribe,
        updating,
    }
}
