import { ENDPOINTS } from "@/services/api/constants"
import { apiDelete, apiGet, apiPatch, apiPost, apiPostMultipart } from "@/services/api/client"
import type {
    ProductCreate,
    ProductReviewCreate,
    ProductReviewEligibilityRead,
    ProductReviewRead,
    ProductUpdate,
    ProductWithVariantsRead,
} from "@/types/product"

export type ProductApiSort =
    | "newest"
    | "name_asc"
    | "name_desc"
    | "price_asc"
    | "price_desc"

export type GetProductsOptions = {
    categoryId?: number
    q?: string
    minPriority?: number
    limit?: number
    offset?: number
    sort?: ProductApiSort
}

export type GetSimilarProductsOptions = {
    limit?: number
    offset?: number
}

export type GetProductReviewsOptions = {
    limit?: number
    offset?: number
}

export function getProducts({
    categoryId,
    q,
    minPriority,
    limit,
    offset,
    sort,
}: GetProductsOptions = {}): Promise<ProductWithVariantsRead[]> {
    return apiGet<ProductWithVariantsRead[]>(ENDPOINTS.PRODUCTS, {
        category_id: categoryId,
        q,
        min_priority: minPriority,
        limit,
        offset,
        sort,
    })
}

export function getProduct(productId: number): Promise<ProductWithVariantsRead> {
    return apiGet<ProductWithVariantsRead>(`${ENDPOINTS.PRODUCTS}/${productId}`)
}

export function getSimilarProducts(
    productId: number,
    { limit, offset }: GetSimilarProductsOptions = {},
): Promise<ProductWithVariantsRead[]> {
    return apiGet<ProductWithVariantsRead[]>(`${ENDPOINTS.PRODUCTS}/${productId}/similar`, {
        limit,
        offset,
    })
}

export function getProductReviews(
    productId: number,
    { limit, offset }: GetProductReviewsOptions = {},
): Promise<ProductReviewRead[]> {
    return apiGet<ProductReviewRead[]>(`${ENDPOINTS.PRODUCTS}/${productId}/reviews`, {
        limit,
        offset,
    })
}

export function createProductReview(
    productId: number,
    data: ProductReviewCreate,
): Promise<ProductReviewRead> {
    const formData = new FormData()
    formData.append("value", String(data.value))
    if (typeof data.text === "string") {
        formData.append("text", data.text)
    }

    for (const attachment of data.attachments ?? []) {
        formData.append(
            "attachments",
            {
                uri: attachment.uri,
                name: attachment.fileName ?? "review-image.jpg",
                type: attachment.mimeType ?? "image/jpeg",
            } as unknown as Blob,
        )
    }

    return apiPostMultipart<ProductReviewRead>(`${ENDPOINTS.PRODUCTS}/${productId}/reviews`, formData)
}

export function getProductReviewEligibility(productId: number): Promise<ProductReviewEligibilityRead> {
    return apiGet<ProductReviewEligibilityRead>(`${ENDPOINTS.PRODUCTS}/${productId}/reviews/eligibility`)
}

export function createProduct(data: ProductCreate): Promise<ProductWithVariantsRead> {
    return apiPost<ProductWithVariantsRead, ProductCreate>(ENDPOINTS.PRODUCTS, data)
}

export function updateProduct(productId: number, data: ProductUpdate): Promise<ProductWithVariantsRead> {
    return apiPatch<ProductWithVariantsRead, ProductUpdate>(`${ENDPOINTS.PRODUCTS}/${productId}`, data)
}

export function deleteProduct(productId: number): Promise<void> {
    return apiDelete(`${ENDPOINTS.PRODUCTS}/${productId}`)
}
