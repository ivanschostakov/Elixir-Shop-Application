import { useCallback, useEffect, useMemo, useRef } from "react"

import { usePaginatedData } from "@/hooks/shared/use-paginated-data"
import { getProducts } from "@/services/api/products"
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

const RECOMMENDATION_FALLBACK_CATALOG_FETCH_MULTIPLIER = 4

export function useRecommendations({
    surface,
    productId = null,
    draftId = null,
    limit,
    enabled = true,
    deps = [],
}: UseRecommendationsOptions) {
    const pageSize = limit ?? (surface === "home" ? 8 : 6)
    const depsKey = useMemo(
        () => JSON.stringify([surface, productId, draftId, pageSize, ...deps]),
        [deps, draftId, pageSize, productId, surface],
    )
    const catalogOffsetRef = useRef(0)
    const catalogBufferRef = useRef<ProductWithVariantsRead[]>([])
    const deliveredProductIdsRef = useRef<Set<number>>(new Set())
    const recommendationExhaustedRef = useRef(false)

    useEffect(() => {
        catalogOffsetRef.current = 0
        catalogBufferRef.current = []
        deliveredProductIdsRef.current = new Set()
        recommendationExhaustedRef.current = false
    }, [depsKey])

    const fetchRecommendationPage = useCallback(async ({
        limit: pageLimit,
        offset,
    }: {
        limit: number
        offset: number
    }) => {
        if (offset === 0) {
            catalogOffsetRef.current = 0
            catalogBufferRef.current = []
            deliveredProductIdsRef.current = new Set()
            recommendationExhaustedRef.current = false
        }

        const nextProducts: ProductWithVariantsRead[] = []
        const nextProductIds = new Set(deliveredProductIdsRef.current)
        const appendProduct = (product: ProductWithVariantsRead) => {
            if (nextProductIds.has(product.id)) {
                return
            }

            nextProductIds.add(product.id)
            nextProducts.push(product)
        }

        if (!recommendationExhaustedRef.current) {
            const recommendedProducts = await getRecommendations({
                surface,
                productId: productId ?? undefined,
                draftId: draftId ?? undefined,
                limit: pageLimit,
                offset,
            })

            recommendedProducts.forEach(appendProduct)
            if (recommendedProducts.length < pageLimit) {
                recommendationExhaustedRef.current = true
            }
        }

        const consumeCatalogBuffer = () => {
            while (nextProducts.length < pageLimit && catalogBufferRef.current.length) {
                const product = catalogBufferRef.current.shift()
                if (product) {
                    appendProduct(product)
                }
            }
        }

        while (nextProducts.length < pageLimit) {
            consumeCatalogBuffer()
            if (nextProducts.length >= pageLimit) {
                break
            }

            const catalogFetchLimit = pageLimit * RECOMMENDATION_FALLBACK_CATALOG_FETCH_MULTIPLIER
            const catalogProducts = await getProducts({
                limit: catalogFetchLimit,
                offset: catalogOffsetRef.current,
                sort: "newest",
            })

            if (!catalogProducts.length) {
                break
            }

            catalogOffsetRef.current += catalogProducts.length
            catalogBufferRef.current.push(...catalogProducts)
            consumeCatalogBuffer()

            if (catalogProducts.length < catalogFetchLimit) {
                break
            }
        }

        nextProducts.slice(0, pageLimit).forEach((product) => {
            deliveredProductIdsRef.current.add(product.id)
        })

        return nextProducts.slice(0, pageLimit)
    }, [draftId, productId, surface])

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
