import { ENDPOINTS } from "@/services/api/constants"
import { apiGet, apiPost } from "@/services/api/client"
import type {
    GetRecommendationsParams,
    RecommendationsResponse,
    TrackRecommendationCategoryViewPayload,
    TrackRecommendationViewPayload,
} from "@/services/api/recommendations.types"

function recommendationsPath(path: string = "") {
    return `${ENDPOINTS.USERS}/me/recommendations${path}`
}

export function getRecommendations({
    surface,
    productId,
    draftId,
    limit,
    offset,
}: GetRecommendationsParams): Promise<RecommendationsResponse> {
    return apiGet<RecommendationsResponse>(recommendationsPath(), {
        surface,
        product_id: productId,
        draft_id: draftId,
        limit,
        offset,
    })
}

export function trackRecommendationView(payload: TrackRecommendationViewPayload) {
    return apiPost<void, TrackRecommendationViewPayload>(
        recommendationsPath("/views"),
        payload,
    )
}

export function trackRecommendationCategoryView(payload: TrackRecommendationCategoryViewPayload) {
    return apiPost<void, TrackRecommendationCategoryViewPayload>(
        recommendationsPath("/categories/views"),
        payload,
    )
}
