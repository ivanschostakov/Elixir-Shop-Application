import { useAsyncData } from "@/hooks/shared/use-async-data"
import { getSimilarProducts } from "@/services/api/products"
import type { ProductWithVariantsRead } from "@/types/product"

export function useSimilarProducts(productId: number | null, limit: number = 6) {
    const {
        data: products,
        error,
        loading,
        reload,
    } = useAsyncData<ProductWithVariantsRead[]>({
        deps: [productId, limit],
        enabled: Boolean(productId),
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
