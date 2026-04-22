import type { DeliveryCountryCode } from "@/services/api/delivery.types"

export type DeliveryCountriesSelectorProps = {
    countryCodes: readonly DeliveryCountryCode[]
    value: DeliveryCountryCode
    onChange: (countryCode: DeliveryCountryCode) => void
}

export type DeliveryCountryButtonProps = {
    countryCode: DeliveryCountryCode
    isActive: boolean
    onPress: (countryCode: DeliveryCountryCode) => void
}
