import { apiGet, apiPost } from "@/services/api/client"
import { ENDPOINTS } from "@/services/api/constants"
import type { CreateOrderPayload, GetOrdersQuery, OrderRead } from "@/services/api/orders.types"

const ordersEndpoint = `${ENDPOINTS.USERS}/me/orders`

export function createOrder(payload: CreateOrderPayload): Promise<OrderRead> {
    return apiPost<OrderRead, CreateOrderPayload>(ordersEndpoint, payload)
}

export function getOrder(orderId: number): Promise<OrderRead> {
    return apiGet<OrderRead>(`${ordersEndpoint}/${orderId}`)
}

export function getOrders(query: GetOrdersQuery = {}): Promise<OrderRead[]> {
    return apiGet<OrderRead[]>(ordersEndpoint, query)
}
