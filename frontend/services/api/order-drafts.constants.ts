import { ENDPOINTS } from "@/services/api/constants"

export const orderDraftsEndpoint = `${ENDPOINTS.USERS}/me/order-drafts`
export const latestOrderDraftEndpoint = `${orderDraftsEndpoint}/latest`

export function orderDraftOptionsEndpoint(draftId: number) {
    return `${orderDraftsEndpoint}/${draftId}/options`
}
