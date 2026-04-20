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
    sort?: ProductBrowseSort
}

export function useInfiniteProductCatalog({
    categoryId = null,
    enabled = true,
    pageSize = PRODUCT_DISCOVER_PAGE_SIZE,
    sort = "newest",
}: UseInfiniteProductCatalogOptions = {}) {
    const {
        error,
        hasMore,
        items: products,
        loadMore,
        loading,
        loadingMore,
    } = usePaginatedData({
        deps: [categoryId, sort],
        enabled,
        fetchPage: ({ limit, offset }) =>
            getProducts({
                ...buildProductBrowseQueryOptions({
                    categoryId,
                    limit,
                    sort,
                }),
                offset,
            }),
        getKey: (product) => product.id,
        pageSize,
    })

    return { products, loading, loadingMore, error, hasMore, loadMore }
}
