import type { SelectedDeliveryAddress } from "@/hooks/delivery/delivery-address-selection-store.types"
import { translate } from "@/i18n/translations"
import { calculateCdekDelivery } from "@/services/api/delivery"
import type { CdekDeliveryCalculation } from "@/services/api/delivery.types"
import { formatMoney } from "@/utils/formatting"

type DoorDeliveryCalculationInput = Pick<
    SelectedDeliveryAddress,
    "address" | "city" | "countryCode" | "latitude" | "longitude" | "postalCode"
>

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
    _deliveryCalculation: CdekDeliveryCalculation | null | undefined,
    fallbackLabel: string,
) {
    return fallbackLabel
}

export function getPickupPointActionLabel(deliveryCalculation?: CdekDeliveryCalculation | null) {
    return getDeliveryActionLabel(deliveryCalculation, translate("delivery.pickupPointChoose"))
}

export function calculateDoorDelivery({
    address,
    city,
    countryCode,
    latitude,
    longitude,
    postalCode,
}: DoorDeliveryCalculationInput): Promise<CdekDeliveryCalculation> {
    return calculateCdekDelivery({
        latitude,
        longitude,
        mode: "door",
        countryCode,
        postalCode,
        address,
        city,
    })
}
