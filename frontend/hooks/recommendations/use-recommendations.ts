import { usePaginatedData } from "@/hooks/shared/use-paginated-data"
import { getRecommendations } from "@/services/api/recommendations"
import type { RecommendationSurface } from "@/services/api/recommendations.types"
import type { ProductWithVariantsRead } from "@/types/product"

type UseRecommendationsOptions = {
    surface: RecommendationSurface
    productId?: number | null
    draftId?: number | null
    limit?: number
    enabled?: boolean
    deps?: readonly unknown[]
}

export function useRecommendations({
    surface,
    productId = null,
    draftId = null,
    limit,
    enabled = true,
    deps = [],
}: UseRecommendationsOptions) {
    const pageSize = limit ?? (surface === "home" ? 8 : 6)
    const {
        error,
        hasMore,
        items: products,
        loadMore,
        loading,
        loadingMore,
        reload,
    } = usePaginatedData<ProductWithVariantsRead>({
        deps: [surface, productId, draftId, pageSize, ...deps],
        enabled,
        fetchPage: ({ limit: pageLimit, offset }) =>
            getRecommendations({
                surface,
                productId: productId ?? undefined,
                draftId: draftId ?? undefined,
                limit: pageLimit,
                offset,
            }),
        getKey: (product) => product.id,
        pageSize,
    })

    return {
        products,
        error,
        hasMore,
        loadMore,
        loading,
        loadingMore,
        reload,
    }
}
