import { ApiError } from "@/services/api/client"

export function parseDraftId(rawDraftId: string | string[] | undefined) {
    if (Array.isArray(rawDraftId)) {
        return parseDraftId(rawDraftId[0])
    }

    if (!rawDraftId) {
        return null
    }

    const draftId = Number(rawDraftId)
    return Number.isInteger(draftId) && draftId > 0 ? draftId : null
}

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
