import type { DeliveryCountryCode } from "@/services/api/delivery.types"

export type OrderDraftDeliveryMode = "door" | "pickup"
export type OrderDraftDeliveryProvider = "CDEK" | "YANDEX"

export type DeliveryCalculationPayload = {
    delivery_sum: number
    period_min: number
    period_max: number
    currency: string
}

export type UpdateOrderDraftPayload = {
    draft_name?: string | null
    comment?: string | null
    delivery_address_id?: number | null
    recipient_id?: number | null
    new_recipient?: NewRecipientPayload | null
    new_delivery_address?: NewDeliveryAddressPayload | null
    sync_basket_items?: boolean
}

export type NewRecipientPayload = {
    name: string
    surname: string
    phone: string
    email: string
}

export type NewDeliveryAddressPayload = {
    mode?: OrderDraftDeliveryMode | null
    provider?: OrderDraftDeliveryProvider | null
    country_code?: DeliveryCountryCode | null
    name?: string | null
    full_address: string
    details?: string | null
    city?: string | null
    postal_code?: string | null
    latitude?: number | null
    longitude?: number | null
    provider_reference?: string | null
    delivery_calculation?: DeliveryCalculationPayload | null
}

export type CreateOrderDraftPayload = {
    mode?: OrderDraftDeliveryMode | null
    provider?: OrderDraftDeliveryProvider | null
    country_code?: DeliveryCountryCode | null
    name?: string | null
    full_address?: string | null
    details?: string | null
    city?: string | null
    postal_code?: string | null
    latitude?: number | null
    longitude?: number | null
    provider_reference?: string | null
    draft_name?: string | null
    delivery_calculation?: DeliveryCalculationPayload | null
}

export type DeliveryAddressRead = {
    id: number
    user_id: number
    mode: OrderDraftDeliveryMode
    provider: OrderDraftDeliveryProvider
    country_code: DeliveryCountryCode
    name: string
    full_address: string
    details: string | null
    city: string | null
    postal_code: string | null
    latitude: number
    longitude: number
    provider_reference: string | null
    created_at: string
    updated_at: string
}

export type DeliveryRecipientRead = {
    id: number
    user_id: number
    name: string
    surname: string
    phone: string
    email: string
    created_at: string
    updated_at: string
}

export type OrderDraftItemRead = {
    id: number
    user_id: number
    draft_id: number
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

export type OrderDraftRead = {
    id: number
    user_id: number
    delivery_address_id: number | null
    recipient_id: number | null
    status: string
    items_count: number
    total_quantity: number
    basket_subtotal: string
    delivery_total: string
    grand_total: string
    currency: string
    delivery_period_min: number | null
    delivery_period_max: number | null
    draft_name: string | null
    comment: string | null
    delivery_address: DeliveryAddressRead | null
    recipient: DeliveryRecipientRead | null
    items: OrderDraftItemRead[]
    created_at: string
    updated_at: string
}

export type OrderDraftCheckoutOptionsRead = {
    addresses: DeliveryAddressRead[]
    recipients: DeliveryRecipientRead[]
}
