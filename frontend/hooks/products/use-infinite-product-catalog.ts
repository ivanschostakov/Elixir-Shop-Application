import {
    buildProductBrowseQueryOptions,
    PRODUCT_DISCOVER_PAGE_SIZE,
    type ProductBrowseSort,
} from "@/hooks/products/product-browse"
import { usePaginatedData } from "@/hooks/shared/use-paginated-data"
import { getProducts } from "@/services/api/products"
import { useAuth } from "@/providers/auth-provider"

type UseInfiniteProductCatalogOptions = {
    categoryId?: number | null
    enabled?: boolean
    pageSize?: number
    query?: string
    newOnly?: boolean
    sort?: ProductBrowseSort
}

export function useInfiniteProductCatalog({
    categoryId = null,
    enabled = true,
    pageSize = PRODUCT_DISCOVER_PAGE_SIZE,
    query = "",
    newOnly = false,
    sort = "newest",
}: UseInfiniteProductCatalogOptions = {}) {
    const { user, isReady } = useAuth()
    const normalizedQuery = query.trim()
    const {
        error,
        hasMore,
        items: products,
        loadMore,
        loading,
        loadingMore,
        reload,
    } = usePaginatedData({
        deps: [user?.id, categoryId, newOnly, normalizedQuery, sort],
        enabled: enabled && isReady,
        fetchPage: ({ limit, offset }) =>
            getProducts({
                ...buildProductBrowseQueryOptions({
                    categoryId,
                    limit,
                    newOnly,
                    query: normalizedQuery || undefined,
                    sort,
                }),
                offset,
            }),
        getKey: (product) => product.id,
        pageSize,
    })

    return { products, loading, loadingMore, error, hasMore, loadMore, reload }
}
