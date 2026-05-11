import {
    buildProductBrowseQueryOptions,
    PRODUCT_DISCOVER_PAGE_SIZE,
    type ProductBrowseSort,
} from "@/hooks/products/product-browse"
import { usePaginatedData } from "@/hooks/shared/use-paginated-data"
import { getProducts } from "@/services/api/products"

type UseInfiniteProductCatalogOptions = {
    categoryId?: number | null
    enabled?: boolean
    pageSize?: number
    query?: string
    sort?: ProductBrowseSort
}

export function useInfiniteProductCatalog({
    categoryId = null,
    enabled = true,
    pageSize = PRODUCT_DISCOVER_PAGE_SIZE,
    query = "",
    sort = "newest",
}: UseInfiniteProductCatalogOptions = {}) {
    const normalizedQuery = query.trim()
    const {
        error,
        hasMore,
        items: products,
        loadMore,
        loading,
        loadingMore,
    } = usePaginatedData({
        deps: [categoryId, normalizedQuery, sort],
        enabled,
        fetchPage: ({ limit, offset }) =>
            getProducts({
                ...buildProductBrowseQueryOptions({
                    categoryId,
                    limit,
                    query: normalizedQuery || undefined,
                    sort,
                }),
                offset,
            }),
        getKey: (product) => product.id,
        pageSize,
    })

    return { products, loading, loadingMore, error, hasMore, loadMore }
}
