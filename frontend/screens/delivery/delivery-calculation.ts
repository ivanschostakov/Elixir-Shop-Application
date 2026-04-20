import { translate } from "@/i18n/translations"
import type { CdekDeliveryCalculation } from "@/services/api/delivery.types"

function formatMoney(amount?: number | null, currency?: string | null) {
    if (amount === null || amount === undefined) {
        return null
    }

    if (currency) {
        try {
            return new Intl.NumberFormat("ru-RU", {
                style: "currency",
                currency,
                maximumFractionDigits: Number.isInteger(amount) ? 0 : 2,
            }).format(amount)
        } catch {
            return `${amount.toFixed(2)} ${currency}`
        }
    }

    return amount.toFixed(2)
}

function getDayDeclension(days: number) {
    const mod10 = days % 10
    const mod100 = days % 100

    if (mod10 === 1 && mod100 !== 11) {
        return "день"
    }

    if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) {
        return "дня"
    }

    return "дней"
}

export function formatDeliveryCalculationPrice(deliveryCalculation?: CdekDeliveryCalculation | null) {
    if (!deliveryCalculation) {
        return null
    }

    return formatMoney(deliveryCalculation.delivery_sum, deliveryCalculation.currency)
}

export function formatDeliveryCalculationPeriod(deliveryCalculation?: CdekDeliveryCalculation | null) {
    if (!deliveryCalculation) {
        return null
    }

    if (deliveryCalculation.period_min === deliveryCalculation.period_max) {
        return `${deliveryCalculation.period_min} ${getDayDeclension(deliveryCalculation.period_min)}`
    }

    return `${deliveryCalculation.period_min}-${deliveryCalculation.period_max} ${getDayDeclension(deliveryCalculation.period_max)}`
}

export function getDeliveryActionLabel(
    deliveryCalculation: CdekDeliveryCalculation | null | undefined,
    fallbackLabel: string,
) {
    const price = formatDeliveryCalculationPrice(deliveryCalculation)
    const period = formatDeliveryCalculationPeriod(deliveryCalculation)

    if (!price || !period) {
        return fallbackLabel
    }

    return `${price} • ~${period}`
}

export function getPickupPointActionLabel(deliveryCalculation?: CdekDeliveryCalculation | null) {
    return getDeliveryActionLabel(deliveryCalculation, translate("delivery.pickupPointChoose"))
}
