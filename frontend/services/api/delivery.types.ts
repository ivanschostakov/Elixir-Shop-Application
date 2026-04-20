export type DeliveryCountryCode =
    | "RU"
    | "BY"
    | "KZ"
    | "AZ"
    | "MD"
    | "AM"
    | "UZ"
    | "KG"
    | "GE"
    | "MN"
    | "CN"
    | "JP"
    | "RS"
    | "IL"
    | "AE"
    | "IN"
    | "BD"
    | "VN"
    | "TH"
    | "ID"
    | "US"

export type DeliveryPointMarker = {
    code: string
    latitude: number
    longitude: number
}

export type DeliveryPointProvider = "cdek" | "yandex"

export type CdekDeliveryMode = "pickup" | "door" | "office"

export type CdekDeliveryCalculation = {
    delivery_sum: number
    period_min: number
    period_max: number
    weight_calc: number
    currency: string
}

export type CdekDeliveryCalculationRequest = {
    latitude: number
    longitude: number
    mode: CdekDeliveryMode
    countryCode?: DeliveryCountryCode | null
    postalCode?: string | null
    address?: string | null
    city?: string | null
}

export type DeliveryPointMarkerWithProvider = DeliveryPointMarker & {
    provider: DeliveryPointProvider
}

export type DeliveryPointDetails = {
    code: string
    name: string
    address: string
    address_full: string
    city: string
    country_code: DeliveryCountryCode | null
    postal_code: string | null
    latitude: number
    longitude: number
    work_time: string
    phones: string[]
    emails: string[]
    office_image_urls: string[]
    is_handout: boolean
    is_reception: boolean
    have_cashless: boolean
    have_cash: boolean
    nearest_station: string | null
    nearest_metro_station: string | null
    note: string | null
}

export type DeliveryGeoPoint = {
    lat: number
    lon: number
}

export type DeliveryGeoBounds = {
    south_west: DeliveryGeoPoint
    north_east: DeliveryGeoPoint
}

export type DeliveryGeoSuggestResult = {
    type: string
    title: string
    subtitle: string
    full_address: string
    tags: string[]
    uri: string | null
    action: string | null
    button_text: string | null
    distance_text: string | null
    distance_value: number | null
    primary_tag: string | null
    is_business: boolean
    is_toponym: boolean
    display_subtitle: string
    icon_key: string
}

export type DeliveryGeoCodeResult = {
    address: string
    title: string
    subtitle: string
    city: string | null
    kind: string
    precision: string | null
    country_code: string | null
    lat: number
    lon: number
    bounds: DeliveryGeoBounds | null
    uri: string | null
    postal_code: string | null
}
