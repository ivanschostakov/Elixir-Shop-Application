import type { DeliveryGeoSuggestResult } from "@/services/api/delivery.types"

export function getResultTitle(result: DeliveryGeoSuggestResult) {
    return result.title || result.full_address
}

export function getResultSubtitle(result: DeliveryGeoSuggestResult) {
    if (result.display_subtitle) {
        return result.display_subtitle
    }

    return result.full_address !== getResultTitle(result) ? result.full_address : ""
}
