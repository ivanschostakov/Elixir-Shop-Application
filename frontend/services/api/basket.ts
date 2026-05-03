import { apiDelete, apiFetch, apiGet, apiPatch, apiPost } from "@/services/api/client"
import { basketEndpoint, basketItemsEndpoint } from "@/services/api/basket.constants"
import type { OrderDraftCheckoutOptionsRead, UpdateOrderDraftPayload } from "@/services/api/order-drafts.types"
import type { BasketItemCreate, BasketItemUpdate, BasketRead } from "@/types/basket"

export function getBasket(): Promise<BasketRead> {
    return apiGet<BasketRead>(basketEndpoint)
}

export function addBasketItem(payload: BasketItemCreate): Promise<BasketRead> {
    return apiPost<BasketRead, BasketItemCreate>(basketItemsEndpoint, payload)
}

export function updateBasketItem(itemId: number, payload: BasketItemUpdate): Promise<BasketRead> {
    return apiPatch<BasketRead, BasketItemUpdate>(`${basketItemsEndpoint}/${itemId}`, payload)
}

export function removeBasketItem(itemId: number): Promise<BasketRead> {
    return apiDelete<BasketRead>(`${basketItemsEndpoint}/${itemId}`)
}

export function clearBasket(): Promise<BasketRead> {
    return apiDelete<BasketRead>(basketItemsEndpoint)
}

export function getBasketCheckoutOptions(): Promise<OrderDraftCheckoutOptionsRead> {
    return apiGet<OrderDraftCheckoutOptionsRead>(`${basketEndpoint}/checkout/options`)
}

export function updateBasketCheckout(payload: UpdateOrderDraftPayload): Promise<BasketRead> {
    return apiPatch<BasketRead, UpdateOrderDraftPayload>(`${basketEndpoint}/checkout`, payload)
}

export function restoreDraftToBasket(draftId: number): Promise<BasketRead> {
    return apiFetch<BasketRead>(`${basketEndpoint}/restore-draft/${draftId}`, {
        method: "POST",
    })
}
