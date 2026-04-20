import type { GetProductsOptions, ProductApiSort } from "@/services/api/products"

export type ProductBrowseSort = ProductApiSort

export const PRODUCT_BROWSE_LIMIT = 100
export const PRODUCT_DISCOVER_PAGE_SIZE = 24

type BuildProductBrowseQueryOptionsArgs = {
    categoryId?: number | null
    limit?: number
    minPriority?: number
    query?: string
    sort?: ProductBrowseSort
}

export function buildProductBrowseQueryOptions({
    categoryId = null,
    limit = PRODUCT_BROWSE_LIMIT,
    minPriority,
    query,
    sort = "newest",
}: BuildProductBrowseQueryOptionsArgs): GetProductsOptions {
    return {
        categoryId: categoryId ?? undefined,
        limit,
        minPriority,
        q: query,
        sort,
    }
}
