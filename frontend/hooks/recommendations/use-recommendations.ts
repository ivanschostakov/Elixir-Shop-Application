import { useCallback } from "react"

import { usePaginatedData } from "@/hooks/shared/use-paginated-data"
import { useAuth } from "@/providers/auth-provider"
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
    const { isAuthenticated } = useAuth()
    const pageSize = limit ?? (surface === "home" ? 8 : 6)

    const fetchRecommendationPage = useCallback(async ({
        limit: pageLimit,
        offset,
    }: {
        limit: number
        offset: number
    }) =>
        getRecommendations({
            surface,
            productId: productId ?? undefined,
            draftId: draftId ?? undefined,
            limit: pageLimit,
            offset,
        }),
        [draftId, productId, surface],
    )

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
        enabled: enabled && isAuthenticated,
        fetchPage: fetchRecommendationPage,
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
