import type {
    CdekDeliveryCalculation,
    DeliveryCountryCode,
    DeliveryPointProvider,
} from "@/services/api/delivery.types"

export type SelectedDeliveryPoint = {
    code: string
    name: string
    address: string
    address_full: string
    city: string
    countryCode: DeliveryCountryCode | null
    latitude: number
    longitude: number
    postalCode: string | null
    work_time: string
    phones: string[]
    emails: string[]
    provider: DeliveryPointProvider
    deliveryCalculation: CdekDeliveryCalculation | null
}
