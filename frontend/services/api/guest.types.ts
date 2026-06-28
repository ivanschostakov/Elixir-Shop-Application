import type {
    DeliveryCalculationPayload,
    NewDeliveryAddressPayload,
    NewRecipientPayload,
} from "@/services/api/order-drafts.types"
import type { CreateOrderPayload, OrderRead } from "@/services/api/orders.types"
import type { AuthTokensWithUserResponse } from "@/services/auth/auth.types"
import type { BasketRead } from "@/types/basket"

export type GuestBasketItemPayload = {
    variant_id: number
    quantity: number
}

export type GuestBasketQuotePayload = {
    items: GuestBasketItemPayload[]
}

export type GuestBasketQuoteRead = BasketRead

export type GuestDeliveryAddressPayload = Omit<NewDeliveryAddressPayload, "delivery_calculation"> & {
    delivery_calculation: DeliveryCalculationPayload
}

export type GuestOrderPayload = {
    items: GuestBasketItemPayload[]
    delivery_address: GuestDeliveryAddressPayload
    recipient: NewRecipientPayload
    payment_method: CreateOrderPayload["payment_method"]
}

export type GuestOrderResponse = AuthTokensWithUserResponse & {
    order: OrderRead
}

export type GuestPhoneCheckPayload = {
    phone_number: string
}

export type GuestPhoneCheckResponse = {
    phone_number: string
    exists: boolean
}
