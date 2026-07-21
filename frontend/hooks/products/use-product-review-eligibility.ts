import { useAsyncData } from "@/hooks/shared/use-async-data"
import { getProductReviewEligibility } from "@/services/api/products"

function assertValidProductId(productId: number) {
    if (!productId || !Number.isFinite(productId)) {
        throw new Error("Invalid product id")
    }
}

export function useProductReviewEligibility(productId: number) {
    const { data, error, loading, reload } = useAsyncData({
        deps: [productId],
        enabled: Boolean(productId && Number.isFinite(productId)),
        fetcher: async () => {
            assertValidProductId(productId)
            return getProductReviewEligibility(productId)
        },
        initialData: { can_review: false },
        resetOnLoad: true,
    })

    return {
        canReview: data.can_review,
        error,
        loading,
        reload,
    }
}
