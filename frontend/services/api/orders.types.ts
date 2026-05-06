import type { DeliveryAddressRead, DeliveryRecipientRead } from "@/services/api/order-drafts.types"

export type OrderHistoryBucket = "active" | "completed"
export type OrderStatusCode =
    | "created"
    | "invoice_sent"
    | "paid"
    | "waiting_response"
    | "packaged"
    | "sent"
    | "delivered"
    | "canceled"
    | "completed"
    | "refund_declined"

export type OrderItemRead = {
    id: number
    user_id: number
    order_id: number
    product_id: number
    variant_id: number
    product_name: string
    product_sku: string
    variant_name: string
    variant_sku: string | null
    quantity: number
    unit_price: string
    line_total: string
    image_url: string
    created_at: string
    updated_at: string
}

export type OrderRead = {
    id: number
    order_code: string
    order_number: string
    draft_id: number | null
    user_id: number
    delivery_address_id: number
    recipient_id: number
    status: string
    status_code: OrderStatusCode
    history_bucket: OrderHistoryBucket
    items_count: number
    total_quantity: number
    basket_subtotal: string
    delivery_total: string
    grand_total: string
    currency: string
    delivery_period_min: number | null
    delivery_period_max: number | null
    comment: string | null
    delivery_string: string | null
    selected_delivery_service: string
    selected_delivery_payload: Record<string, unknown>
    checkout_snapshot: Record<string, unknown>
    payment_method: string | null
    payment_provider: string | null
    payment_status: string
    payment_invoice_id: string | null
    payment_paid_at: string | null
    payment_error: string | null
    amocrm_lead_id: number | null
    delivery_created_at: string | null
    delivery_provider_ref: string | null
    yandex_request_id: string | null
    is_active: boolean
    is_paid: boolean
    is_canceled: boolean
    is_shipped: boolean
    delivery_address: DeliveryAddressRead
    recipient: DeliveryRecipientRead
    items: OrderItemRead[]
    created_at: string
    updated_at: string
}

export type CreateOrderPayload = {
    draft_id?: number | null
    payment_method: "later" | "sbp"
    code?: string | null
    requested_deposit_amount?: string | null
}

export type GetOrdersQuery = {
    limit?: number
    offset?: number
    history_bucket?: OrderHistoryBucket
    status_code?: OrderStatusCode | null
    created_from?: string | null
    created_to?: string | null
}
