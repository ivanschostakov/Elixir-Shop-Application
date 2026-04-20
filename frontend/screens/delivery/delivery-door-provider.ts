import type { ImageSourcePropType } from "react-native"

import { translate } from "@/i18n/translations"
import type { SelectedDeliveryAddress } from "@/hooks/delivery/delivery-address-selection-store.types"
import { calculateCdekDelivery } from "@/services/api/delivery"
import type {
    CdekDeliveryCalculation,
    DeliveryCountryCode,
    DeliveryPointProvider,
} from "@/services/api/delivery.types"

type DoorDeliveryCalculationInput = Pick<
    SelectedDeliveryAddress,
    "address" | "city" | "countryCode" | "latitude" | "longitude" | "postalCode" | "provider"
>

export type DoorDeliveryProviderOption = {
    key: DeliveryPointProvider
    label: string
    imageAlt: string
    imageSource: ImageSourcePropType
}

const DOOR_DELIVERY_PROVIDER_IMAGES: Record<DeliveryPointProvider, ImageSourcePropType> = {
    cdek: require("@/assets/icons/delivery-services/cdek-door.png"),
    yandex: require("@/assets/icons/delivery-services/yandex-door.png"),
}

export function getAvailableDoorDeliveryProviders(_countryCode: DeliveryCountryCode) {
    return ["cdek"] satisfies DeliveryPointProvider[]
}

export function normalizeDoorDeliveryProvider(
    provider: DeliveryPointProvider | null | undefined,
    countryCode: DeliveryCountryCode,
): DeliveryPointProvider {
    const availableProviders = getAvailableDoorDeliveryProviders(countryCode)

    if (provider && availableProviders.includes(provider)) {
        return provider
    }

    return availableProviders[0]
}

export function getDoorDeliveryProviderLabel(provider: DeliveryPointProvider) {
    return provider === "yandex"
        ? translate("delivery.providerYandex")
        : translate("delivery.providerCdek")
}

export function getDoorDeliveryProviderImage(provider: DeliveryPointProvider) {
    return DOOR_DELIVERY_PROVIDER_IMAGES[provider]
}

export function getDoorDeliveryProviderAlt(provider: DeliveryPointProvider) {
    return `${getDoorDeliveryProviderLabel(provider)} ${translate("delivery.doorDeliveryTitle")}`
}

export function getDoorDeliveryProviderOptions(countryCode: DeliveryCountryCode): DoorDeliveryProviderOption[] {
    return getAvailableDoorDeliveryProviders(countryCode).map((provider) => ({
        key: provider,
        label: getDoorDeliveryProviderLabel(provider),
        imageAlt: getDoorDeliveryProviderAlt(provider),
        imageSource: getDoorDeliveryProviderImage(provider),
    }))
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
