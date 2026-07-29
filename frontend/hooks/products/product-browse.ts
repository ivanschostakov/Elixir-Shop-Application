import type { GetProductsOptions, ProductApiSort } from "@/services/api/products"

export type ProductBrowseSort = ProductApiSort

export const PRODUCT_BROWSE_LIMIT = 100
export const PRODUCT_DISCOVER_PAGE_SIZE = 16

type BuildProductBrowseQueryOptionsArgs = {
    categoryId?: number | null
    limit?: number
    minPriority?: number
    newOnly?: boolean
    query?: string
    sort?: ProductBrowseSort
}

export function buildProductBrowseQueryOptions({
    categoryId = null,
    limit = PRODUCT_BROWSE_LIMIT,
    minPriority,
    newOnly,
    query,
    sort = "newest",
}: BuildProductBrowseQueryOptionsArgs): GetProductsOptions {
    return {
        categoryId: categoryId ?? undefined,
        limit,
        minPriority,
        newOnly,
        q: query,
        sort,
    }
}
