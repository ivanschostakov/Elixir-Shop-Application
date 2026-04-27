import type { CdekDeliveryCalculation, DeliveryPointProvider } from "@/services/api/delivery.types"
import type { DeliveryCalculationPayload, OrderDraftDeliveryProvider } from "@/services/api/order-drafts.types"

export function getOrderDraftProvider(provider: DeliveryPointProvider): OrderDraftDeliveryProvider {
    return provider === "yandex" ? "YANDEX" : "CDEK"
}

export function buildOrderDraftCalculationPayload(deliveryCalculation: CdekDeliveryCalculation): DeliveryCalculationPayload {
    return {
        delivery_sum: deliveryCalculation.delivery_sum,
        period_min: deliveryCalculation.period_min,
        period_max: deliveryCalculation.period_max,
        currency: deliveryCalculation.currency,
    }
}

export function getPickupPointAddressValue(addressFull?: string | null, address?: string | null) {
    return addressFull || address || ""
}
