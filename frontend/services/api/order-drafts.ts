import { apiDelete, apiGet, apiPatch, apiPost } from "@/services/api/client"
import { latestOrderDraftEndpoint, orderDraftOptionsEndpoint, orderDraftsEndpoint } from "@/services/api/order-drafts.constants"
import type {
    CreateOrderDraftPayload,
    OrderDraftCheckoutOptionsRead,
    OrderDraftRead,
    UpdateOrderDraftPayload,
} from "@/services/api/order-drafts.types"

export function createOrderDraft(payload: CreateOrderDraftPayload): Promise<OrderDraftRead> {
    return apiPost<OrderDraftRead, CreateOrderDraftPayload>(orderDraftsEndpoint, payload)
}

export function getOrderDrafts(limit = 6): Promise<OrderDraftRead[]> {
    return apiGet<OrderDraftRead[]>(orderDraftsEndpoint, { limit })
}

export function getLatestOrderDraft(): Promise<OrderDraftRead> {
    return apiGet<OrderDraftRead>(latestOrderDraftEndpoint)
}

export function getOrderDraft(draftId: number): Promise<OrderDraftRead> {
    return apiGet<OrderDraftRead>(`${orderDraftsEndpoint}/${draftId}`)
}

export function getOrderDraftOptions(draftId: number): Promise<OrderDraftCheckoutOptionsRead> {
    return apiGet<OrderDraftCheckoutOptionsRead>(orderDraftOptionsEndpoint(draftId))
}

export function updateOrderDraft(draftId: number, payload: UpdateOrderDraftPayload): Promise<OrderDraftRead> {
    return apiPatch<OrderDraftRead, UpdateOrderDraftPayload>(`${orderDraftsEndpoint}/${draftId}`, payload)
}

export function deleteOrderDraft(draftId: number): Promise<void> {
    return apiDelete(`${orderDraftsEndpoint}/${draftId}`)
}
