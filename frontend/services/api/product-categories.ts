import { ENDPOINTS } from "@/services/api/constants"
import { apiGet } from "@/services/api/client"
import type { ProductCategory } from "@/types/product-category"

export type ProductCategoryApiSort = "newest" | "name_asc" | "name_desc"

export type GetProductCategoriesOptions = {
    q?: string
    limit?: number
    offset?: number
    sort?: ProductCategoryApiSort
}

export function getProductCategories({
    q,
    limit,
    offset,
    sort = "name_asc",
}: GetProductCategoriesOptions = {}): Promise<ProductCategory[]> {
    return apiGet<ProductCategory[]>(ENDPOINTS.PRODUCT_CATEGORIES, { q, limit, offset, sort })
}
