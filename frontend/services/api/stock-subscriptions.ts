import { apiDelete, apiGet, apiPost } from "@/services/api/client"

const productStockSubscriptionsEndpoint = "/users/me/stock-subscriptions/products"

export type ProductStockSubscriptionStatus = {
    product_id: number
    is_subscribed: boolean
}

export function getProductStockSubscriptionStatus(
    productId: number,
): Promise<ProductStockSubscriptionStatus> {
    return apiGet<ProductStockSubscriptionStatus>(
        `${productStockSubscriptionsEndpoint}/${productId}`,
    )
}

export function subscribeToProductStock(
    productId: number,
): Promise<ProductStockSubscriptionStatus> {
    return apiPost<ProductStockSubscriptionStatus, Record<string, never>>(
        `${productStockSubscriptionsEndpoint}/${productId}`,
        {},
    )
}

export function unsubscribeFromProductStock(productId: number): Promise<void> {
    return apiDelete(`${productStockSubscriptionsEndpoint}/${productId}`)
}
