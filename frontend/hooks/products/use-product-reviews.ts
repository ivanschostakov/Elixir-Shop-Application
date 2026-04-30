import { useAsyncData } from "@/hooks/shared/use-async-data"
import { getProductReviews } from "@/services/api/products"
import type { UseProductReviewsResult } from "@/hooks/products/use-product-reviews.types"

function assertValidProductId(productId: number) {
    if (!productId || !Number.isFinite(productId)) {
        throw new Error("Invalid product id")
    }
}

export function useProductReviews(productId: number): UseProductReviewsResult {
    const { data: reviews, error, loading, reload, setData } = useAsyncData({
        deps: [productId],
        fetcher: async () => {
            assertValidProductId(productId)
            return getProductReviews(productId)
        },
        initialData: [],
        resetOnLoad: true,
    })

    return { reviews, loading, error, reload, setReviews: setData }
}
