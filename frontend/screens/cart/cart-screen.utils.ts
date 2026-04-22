import { ApiError } from "@/services/api/client"
import type {
    CdekDeliveryCalculation,
    DeliveryPointProvider,
} from "@/services/api/delivery.types"
import type { DeliveryCalculationPayload } from "@/services/api/order-drafts.types"

type CartErrorTranslationKey =
    | "cart.itemMissing"
    | "cart.loadFailedMessage"
    | "cart.stockConflict"
    | "cart.updateFailed"

type CartErrorTranslator = (key: CartErrorTranslationKey) => string

export function getBasketErrorMessage(
    error: unknown,
    fallbackMessage: string | null,
    t: CartErrorTranslator,
) {
    if (error instanceof ApiError) {
        if (error.status === 404) {
            return t("cart.itemMissing")
        }

        if (error.status === 409) {
            return t("cart.stockConflict")
        }
    }

    return error instanceof Error ? error.message : fallbackMessage ?? t("cart.updateFailed")
}

export function getOrderDraftProvider(provider: DeliveryPointProvider) {
    return provider === "yandex" ? "YANDEX" : "CDEK"
}

export function buildOrderDraftCalculationPayload(
    deliveryCalculation: CdekDeliveryCalculation,
): DeliveryCalculationPayload {
    return {
        delivery_sum: deliveryCalculation.delivery_sum,
        period_min: deliveryCalculation.period_min,
        period_max: deliveryCalculation.period_max,
        currency: deliveryCalculation.currency,
    }
}

export function buildPickupPointAddress(addressFull: string, address: string) {
    return addressFull || address
}

export function formatSavedCartDraftName(date: Date) {
    const hours = String(date.getHours()).padStart(2, "0")
    const minutes = String(date.getMinutes()).padStart(2, "0")
    const day = String(date.getDate()).padStart(2, "0")
    const month = String(date.getMonth() + 1).padStart(2, "0")

    return `Корзина от ${hours}:${minutes} ${day}.${month}`
}
