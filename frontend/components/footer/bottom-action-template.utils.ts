import { ApiError } from "@/services/api/client"

export { parseDraftId } from "@/utils/route-params"

export function getExistingDraftIdFromError(error: ApiError) {
    const body = error.body
    if (!body || typeof body !== "object" || !("detail" in body)) {
        return null
    }

    const detail = body.detail
    if (!detail || typeof detail !== "object" || !("draft_id" in detail)) {
        return null
    }

    const draftId = Number(detail.draft_id)
    return Number.isInteger(draftId) && draftId > 0 ? draftId : null
}
