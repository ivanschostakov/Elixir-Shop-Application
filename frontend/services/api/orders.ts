import { apiGet, apiPost } from "@/services/api/client"
import { ENDPOINTS } from "@/services/api/constants"
import type { OrderDraftRead } from "@/services/api/order-drafts.types"
import type { CreateOrderPayload, GetOrdersQuery, OrderRead } from "@/services/api/orders.types"

const ordersEndpoint = `${ENDPOINTS.USERS}/me/orders`

export function createOrder(payload: CreateOrderPayload): Promise<OrderRead> {
    return apiPost<OrderRead, CreateOrderPayload>(ordersEndpoint, payload, { appIntegrityAction: "orders:create" })
}

export function getOrder(orderId: number): Promise<OrderRead> {
    return apiGet<OrderRead>(`${ordersEndpoint}/${orderId}`, undefined, { appIntegrityAction: "orders:read" })
}

export function getOrders(query: GetOrdersQuery = {}): Promise<OrderRead[]> {
    return apiGet<OrderRead[]>(ordersEndpoint, query, { appIntegrityAction: "orders:list" })
}

export function repeatOrder(orderId: number): Promise<OrderDraftRead> {
    return apiPost<OrderDraftRead, Record<string, never>>(`${ordersEndpoint}/${orderId}/repeat`, {}, { appIntegrityAction: "orders:repeat" })
}
