import {
    buildProductBrowseQueryOptions,
    type ProductBrowseSort,
} from "@/hooks/products/product-browse"
import { useAsyncData } from "@/hooks/shared/use-async-data"
import { getProducts } from "@/services/api/products"
import type { ProductWithVariantsRead } from "@/types/product"

type UseProductCatalogOptions = {
    categoryId?: number | null
    debounceMs?: number
    enabled?: boolean
    limit?: number
    minPriority?: number
    query?: string
    skipEmptyQuery?: boolean
    sort?: ProductBrowseSort
}

export function useProductCatalog({
    categoryId = null,
    debounceMs = 0,
    enabled = true,
    limit,
    minPriority,
    query = "",
    skipEmptyQuery = false,
    sort = "newest",
}: UseProductCatalogOptions = {}) {
    const normalizedQuery = query.trim()
    const isEnabled = enabled && (!skipEmptyQuery || normalizedQuery.length > 0)
    const { data: products, error, loading } = useAsyncData<ProductWithVariantsRead[]>({
        debounceMs,
        deps: [categoryId, limit, minPriority, normalizedQuery, sort],
        enabled: isEnabled,
        fetcher: () =>
            getProducts(
                buildProductBrowseQueryOptions({
                    categoryId,
                    limit,
                    minPriority,
                    query: normalizedQuery || undefined,
                    sort,
                })
            ),
        initialData: [],
    })

    return { products, loading, error }
}
