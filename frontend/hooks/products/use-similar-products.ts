import { useAsyncData } from "@/hooks/shared/use-async-data"
import { getSimilarProducts } from "@/services/api/products"
import { useAuth } from "@/providers/auth-provider"
import type { ProductWithVariantsRead } from "@/types/product"

export function useSimilarProducts(productId: number | null, limit: number = 6) {
    const { user, isReady } = useAuth()
    const {
        data: products,
        error,
        loading,
        reload,
    } = useAsyncData<ProductWithVariantsRead[]>({
        deps: [user?.id, productId, limit],
        enabled: Boolean(productId) && isReady,
        fetcher: async () => getSimilarProducts(productId as number, { limit }),
        initialData: [],
        resetOnLoad: true,
    })

    return {
        products,
        error,
        loading,
        reload,
    }
}
