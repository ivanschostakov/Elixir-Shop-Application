import type { DeliveryAddressRead, DeliveryRecipientRead } from "@/services/api/order-drafts.types"

export type BasketItemCreate = {
    variant_id: number
    quantity: number
}

export type BasketItemUpdate = {
    quantity: number
}

export type BasketProductSummaryRead = {
    id: number
    sku: string
    name: string
    in_stock: boolean
    image_url: string
}

export type BasketVariantSummaryRead = {
    id: number
    sku: string | null
    name: string
    stock: number
    price: string
    image_url: string
}

export type BasketItemRead = {
    id: number
    variant_id: number
    quantity: number
    unit_price: string
    line_total: string
    available_quantity: number
    is_available: boolean
    product: BasketProductSummaryRead
    variant: BasketVariantSummaryRead
    created_at: string
    updated_at: string
}

export type BasketRead = {
    id: number
    user_id: number
    items: BasketItemRead[]
    delivery_address_id: number | null
    recipient_id: number | null
    delivery_address: DeliveryAddressRead | null
    recipient: DeliveryRecipientRead | null
    items_count: number
    total_quantity: number
    total_amount: string
    delivery_total: string
    grand_total: string
    currency: string
    delivery_period_min: number | null
    delivery_period_max: number | null
    has_unavailable_items: boolean
    created_at: string
    updated_at: string
}
