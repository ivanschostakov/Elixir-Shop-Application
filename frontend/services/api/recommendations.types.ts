import type { ProductWithVariantsRead } from "@/types/product"

export type RecommendationSurface = "home" | "product" | "cart" | "draft"

export type GetRecommendationsParams = {
    surface: RecommendationSurface
    productId?: number
    draftId?: number
    limit?: number
    offset?: number
}

export type TrackRecommendationViewPayload = {
    product_id: number
    variant_id?: number
}

export type TrackRecommendationCategoryViewPayload = {
    category_id: number
}

export type RecommendationsResponse = ProductWithVariantsRead[]
