import { useAsyncData } from "@/hooks/shared/use-async-data"
import { getProduct } from "@/services/api/products"
import { useAuth } from "@/providers/auth-provider"
import type { UseProductResult } from "@/hooks/products/use-product.types"

function assertValidProductId(productId: number) {
    if (!productId || !Number.isFinite(productId)) {
        throw new Error("Invalid product id")
    }
}

export function useProduct(productId: number): UseProductResult {
    const { user, isReady } = useAuth()
    const { data: product, error, loading } = useAsyncData({
        deps: [user?.id, productId],
        enabled: isReady,
        fetcher: async () => {
            assertValidProductId(productId)
            return getProduct(productId)
        },
        initialData: null,
        resetOnLoad: true,
    })

    return { product, loading, error }
}
