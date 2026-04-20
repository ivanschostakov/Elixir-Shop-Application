import { ENDPOINTS } from "@/services/api/constants"
import { apiGet } from "@/services/api/client"
import type {
    CdekDeliveryCalculation,
    CdekDeliveryCalculationRequest,
    DeliveryCountryCode,
    DeliveryGeoCodeResult,
    DeliveryGeoPoint,
    DeliveryGeoSuggestResult,
    DeliveryPointDetails,
    DeliveryPointMarker,
} from "@/services/api/delivery.types"

const DEFAULT_DELIVERY_GEO_LANGUAGE = "ru_RU"
export const DEFAULT_DELIVERY_COUNTRY_CODE: DeliveryCountryCode = "RU"

function deliveryPath(path: string) {
    return `${ENDPOINTS.DELIVERY}${path}`
}

function formatDeliveryGeoPoint(point: DeliveryGeoPoint) {
    return `${point.lon},${point.lat}`
}

export function getCdekDeliveryPointMarkers(
    countryCode: DeliveryCountryCode = DEFAULT_DELIVERY_COUNTRY_CODE,
): Promise<DeliveryPointMarker[]> {
    return apiGet<DeliveryPointMarker[]>(deliveryPath("/cdek/delivery-point-markers"), {
        country_code: countryCode,
    })
}

export function getCdekDeliveryPoint(code: string): Promise<DeliveryPointDetails> {
    return apiGet<DeliveryPointDetails>(deliveryPath(`/cdek/delivery-point/${encodeURIComponent(code)}`))
}

export function calculateCdekDelivery({
    latitude,
    longitude,
    mode,
    countryCode,
    postalCode,
    address,
    city,
}: CdekDeliveryCalculationRequest): Promise<CdekDeliveryCalculation> {
    return apiGet<CdekDeliveryCalculation>(deliveryPath("/cdek/calculate"), {
        latitude,
        longitude,
        mode,
        country_code: countryCode,
        postal_code: postalCode,
        address,
        city,
    })
}

type YandexDeliveryCalculationResponse = {
    delivery_days: number
    pricing_total: string
    price?: number | string
}

function extractYandexDeliveryCurrency(rawCalculation: YandexDeliveryCalculationResponse) {
    const match = rawCalculation.pricing_total.match(/([A-Z]{3})$/)
    return match?.[1] ?? "RUB"
}

function extractYandexDeliverySum(rawCalculation: YandexDeliveryCalculationResponse) {
    if (rawCalculation.price !== undefined) {
        const numericPrice = Number(rawCalculation.price)

        if (Number.isFinite(numericPrice)) {
            return numericPrice
        }
    }

    const numericPricingTotal = Number(rawCalculation.pricing_total.replace(/[^\d.,-]/g, "").replace(",", "."))

    if (Number.isFinite(numericPricingTotal)) {
        return numericPricingTotal
    }

    throw new Error("Failed to parse Yandex delivery price.")
}

export function calculateYandexDelivery(destination: string): Promise<CdekDeliveryCalculation> {
    return apiGet<YandexDeliveryCalculationResponse>(deliveryPath("/yandex/calculate"), {
        destination,
    }).then((rawCalculation) => ({
        delivery_sum: extractYandexDeliverySum(rawCalculation),
        period_min: rawCalculation.delivery_days,
        period_max: rawCalculation.delivery_days,
        weight_calc: 0,
        currency: extractYandexDeliveryCurrency(rawCalculation),
    }))
}

export function getYandexDeliveryPointMarkers(): Promise<DeliveryPointMarker[]> {
    return apiGet<DeliveryPointMarker[]>(deliveryPath("/yandex/delivery-point-markers"))
}

export function getYandexDeliveryPoint(code: string): Promise<DeliveryPointDetails> {
    return apiGet<DeliveryPointDetails>(deliveryPath(`/yandex/delivery-point/${encodeURIComponent(code)}`))
}

export function suggestDeliveryGeo(
    query: string,
    point: DeliveryGeoPoint,
    lang = DEFAULT_DELIVERY_GEO_LANGUAGE,
): Promise<DeliveryGeoSuggestResult[]> {
    return apiGet<DeliveryGeoSuggestResult[]>(deliveryPath("/geo/suggest"), {
        query,
        ll: formatDeliveryGeoPoint(point),
        lang,
    })
}

export function geocodeDeliveryAddress(
    address: string,
    options: {
        lang?: string
        uri?: string | null
    } = {},
): Promise<DeliveryGeoCodeResult> {
    const { lang = DEFAULT_DELIVERY_GEO_LANGUAGE, uri } = options

    return apiGet<DeliveryGeoCodeResult>(deliveryPath("/geo/code"), {
        address,
        lang,
        results: 1,
        ...(uri ? { uri } : {}),
    })
}

export function reverseGeocodeDeliveryPoint(
    point: DeliveryGeoPoint,
    options: {
        lang?: string
    } = {},
): Promise<DeliveryGeoCodeResult> {
    return geocodeDeliveryAddress(formatDeliveryGeoPoint(point), options)
}
