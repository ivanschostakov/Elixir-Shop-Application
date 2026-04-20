import type {
    CdekDeliveryCalculation,
    DeliveryCountryCode,
    DeliveryPointProvider,
} from "@/services/api/delivery.types"

export type SelectedDeliveryAddress = {
    address: string
    city: string | null
    countryCode: DeliveryCountryCode | null
    provider: DeliveryPointProvider
    latitude: number
    longitude: number
    postalCode: string | null
    subtitle: string
    deliveryCalculation: CdekDeliveryCalculation | null
}
