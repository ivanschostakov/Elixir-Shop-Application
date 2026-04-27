import type { CameraPosition, Point } from "react-native-yamap"

import { translate } from "@/i18n/translations"
import {
    DEFAULT_DELIVERY_COUNTRY_CODE,
} from "@/services/api/delivery"
import type {
    CdekDeliveryCalculation,
    DeliveryCountryCode,
    DeliveryGeoCodeResult,
    DeliveryPointDetails,
    DeliveryPointProvider,
} from "@/services/api/delivery.types"
import type {
    CreateOrderDraftPayload,
    UpdateOrderDraftPayload,
} from "@/services/api/order-drafts.types"
import { DOOR_DELIVERY_PROVIDER } from "@/screens/delivery/delivery-screen.constants"
import type {
    DeliveryDoorDraft,
    DeliveryInfoRow,
    DeliveryMapMarker,
    DeliveryPickupDraft,
} from "@/screens/delivery/delivery-screen.types"
import type { SelectedDeliveryPoint } from "@/hooks/delivery/delivery-point-selection-store.types"
import { buildOrderDraftCalculationPayload, getOrderDraftProvider, getPickupPointAddressValue } from "@/utils/order-drafts"
export { parseBooleanSearchParam, parseDraftId } from "@/utils/route-params"

type PointLike = Pick<Point, "lat" | "lon">
type DeliveryPointWithProvider = DeliveryPointDetails & { provider?: DeliveryPointProvider }

export function getClusteredMarkerPayload(rawData: unknown) {
    const code =
        rawData && typeof rawData === "object" && "code" in rawData && typeof rawData.code === "string"
            ? rawData.code
            : null
    const provider: DeliveryPointProvider =
        rawData && typeof rawData === "object" && "provider" in rawData && rawData.provider === "yandex"
            ? "yandex"
            : "cdek"

    return code
        ? {
              code,
              provider,
          }
        : null
}

export function buildDoorDeliveryDraft(
    geocodeResult: DeliveryGeoCodeResult,
    countryCode: DeliveryCountryCode | null,
): DeliveryDoorDraft {
    return {
        address:
            geocodeResult.address
            || [geocodeResult.title, geocodeResult.subtitle].filter(Boolean).join(", "),
        city: geocodeResult.city,
        countryCode,
        deliveryCalculation: null,
        latitude: geocodeResult.lat,
        longitude: geocodeResult.lon,
        postalCode: geocodeResult.postal_code,
        provider: DOOR_DELIVERY_PROVIDER,
        subtitle: geocodeResult.subtitle,
    }
}

export function buildPickupPointDraft(
    deliveryPoint: DeliveryPointWithProvider | SelectedDeliveryPoint | DeliveryPickupDraft,
): DeliveryPickupDraft {
    return {
        address: deliveryPoint.address,
        address_full: deliveryPoint.address_full,
        city: deliveryPoint.city,
        code: deliveryPoint.code,
        countryCode:
            "country_code" in deliveryPoint ? deliveryPoint.country_code : deliveryPoint.countryCode ?? null,
        latitude: deliveryPoint.latitude,
        longitude: deliveryPoint.longitude,
        name: deliveryPoint.name,
        postalCode:
            "postal_code" in deliveryPoint ? deliveryPoint.postal_code : deliveryPoint.postalCode ?? null,
        provider: deliveryPoint.provider ?? "cdek",
        nearest_metro_station:
            "nearest_metro_station" in deliveryPoint ? deliveryPoint.nearest_metro_station : null,
        nearest_station: "nearest_station" in deliveryPoint ? deliveryPoint.nearest_station : null,
        note: "note" in deliveryPoint ? deliveryPoint.note : null,
        emails: "emails" in deliveryPoint ? deliveryPoint.emails : [],
        phones: "phones" in deliveryPoint ? deliveryPoint.phones : [],
        work_time: deliveryPoint.work_time,
        deliveryCalculation: "deliveryCalculation" in deliveryPoint ? deliveryPoint.deliveryCalculation : null,
    }
}

export function buildSelectedDeliveryPoint(
    pickupPointDraft: DeliveryPickupDraft,
    deliveryCalculation: CdekDeliveryCalculation | null,
): SelectedDeliveryPoint {
    return {
        address: pickupPointDraft.address,
        address_full: pickupPointDraft.address_full,
        city: pickupPointDraft.city,
        code: pickupPointDraft.code,
        countryCode: pickupPointDraft.countryCode,
        latitude: pickupPointDraft.latitude,
        longitude: pickupPointDraft.longitude,
        name: pickupPointDraft.name,
        postalCode: pickupPointDraft.postalCode,
        work_time: pickupPointDraft.work_time,
        phones: pickupPointDraft.phones ?? [],
        emails: pickupPointDraft.emails ?? [],
        provider: pickupPointDraft.provider,
        deliveryCalculation,
    }
}

export function getDeliveryCalculationErrorMessage(deliveryCalculationError: unknown) {
    return deliveryCalculationError instanceof Error
        ? deliveryCalculationError.message
        : translate("delivery.calculateError")
}

export function buildCdekPickupCalculationRequest(
    pickupPointDraft: DeliveryPickupDraft,
    fallbackCountryCode: DeliveryCountryCode | null,
) {
    return {
        latitude: pickupPointDraft.latitude,
        longitude: pickupPointDraft.longitude,
        mode: "office" as const,
        countryCode: pickupPointDraft.countryCode ?? fallbackCountryCode,
        postalCode: pickupPointDraft.postalCode,
        address: pickupPointDraft.address_full || pickupPointDraft.address,
        city: pickupPointDraft.city,
    }
}

export function buildPickupOrderDraftPayload(
    pickupPointDraft: DeliveryPickupDraft,
    deliveryCalculation: CdekDeliveryCalculation,
    fallbackCountryCode: DeliveryCountryCode | null,
): CreateOrderDraftPayload {
    return {
        mode: "pickup",
        provider: getOrderDraftProvider(pickupPointDraft.provider),
        country_code: pickupPointDraft.countryCode ?? fallbackCountryCode ?? DEFAULT_DELIVERY_COUNTRY_CODE,
        name: pickupPointDraft.name,
        full_address: getPickupPointAddress(pickupPointDraft),
        details: pickupPointDraft.work_time || pickupPointDraft.note || null,
        city: pickupPointDraft.city,
        postal_code: pickupPointDraft.postalCode,
        latitude: pickupPointDraft.latitude,
        longitude: pickupPointDraft.longitude,
        provider_reference: pickupPointDraft.code,
        delivery_calculation: buildOrderDraftCalculationPayload(deliveryCalculation),
    }
}

export function buildDoorOrderDraftPayload(
    doorDeliveryDraft: DeliveryDoorDraft,
    deliveryCalculation: CdekDeliveryCalculation,
    fallbackCountryCode: DeliveryCountryCode | null,
): CreateOrderDraftPayload {
    return {
        mode: "door",
        provider: getOrderDraftProvider(doorDeliveryDraft.provider),
        country_code: doorDeliveryDraft.countryCode ?? fallbackCountryCode ?? DEFAULT_DELIVERY_COUNTRY_CODE,
        name: doorDeliveryDraft.address,
        full_address: doorDeliveryDraft.address,
        details: doorDeliveryDraft.subtitle || null,
        city: doorDeliveryDraft.city,
        postal_code: doorDeliveryDraft.postalCode,
        latitude: doorDeliveryDraft.latitude,
        longitude: doorDeliveryDraft.longitude,
        provider_reference: null,
        delivery_calculation: buildOrderDraftCalculationPayload(deliveryCalculation),
    }
}

export function buildOrderDraftAddressUpdatePayload(
    payload: CreateOrderDraftPayload,
    syncBasketItems: boolean,
): UpdateOrderDraftPayload {
    const nextDeliveryAddress = payload as UpdateOrderDraftPayload["new_delivery_address"]

    return syncBasketItems
        ? {
              new_delivery_address: nextDeliveryAddress,
              sync_basket_items: true,
          }
        : {
              new_delivery_address: nextDeliveryAddress,
          }
}

export function getDeliveryPointMarkerKey(provider: DeliveryPointProvider, code: string) {
    return `${provider}:${code}`
}

export function getDoorDeliveryPoint(doorDeliveryDraft: DeliveryDoorDraft | null): Point | null {
    if (!doorDeliveryDraft) {
        return null
    }

    return {
        lat: doorDeliveryDraft.latitude,
        lon: doorDeliveryDraft.longitude,
    }
}

export function getPickupPoint(pickupPointDraft: DeliveryPickupDraft | null): Point | null {
    if (!pickupPointDraft) {
        return null
    }

    return {
        lat: pickupPointDraft.latitude,
        lon: pickupPointDraft.longitude,
    }
}

export function getPickupPointAddress(pickupPointDraft: DeliveryPickupDraft | null) {
    if (!pickupPointDraft) {
        return ""
    }

    return getPickupPointAddressValue(pickupPointDraft.address_full, pickupPointDraft.address)
}

export function getDoorDeliveryInfoRows(doorDeliveryDraft: DeliveryDoorDraft | null) {
    if (!doorDeliveryDraft) {
        return []
    }

    const rows: (DeliveryInfoRow | null)[] = [
        doorDeliveryDraft.subtitle && doorDeliveryDraft.subtitle !== doorDeliveryDraft.address
            ? {
                  key: "subtitle",
                  label: translate("delivery.doorDeliveryTitle"),
                  value: doorDeliveryDraft.subtitle,
              }
            : null,
        doorDeliveryDraft.postalCode
            ? {
                  key: "postal_code",
                  label: translate("delivery.postalCodeLabel"),
                  value: `${translate("delivery.postalCodeLabel")}: ${doorDeliveryDraft.postalCode}`,
              }
            : null,
    ]

    if (!rows.some(Boolean) && doorDeliveryDraft.address) {
        rows.push({
            key: "address",
            label: translate("delivery.pickupPointAddressLabel"),
            value: doorDeliveryDraft.address,
        })
    }

    return rows.filter((row): row is DeliveryInfoRow => row !== null && Boolean(row.value))
}

export function getPickupPointInfoRows(pickupPointDraft: DeliveryPickupDraft | null) {
    if (!pickupPointDraft) {
        return []
    }

    const rows: (DeliveryInfoRow | null)[] = [
        {
            key: "address",
            label: translate("delivery.pickupPointAddressLabel"),
            value: getPickupPointAddress(pickupPointDraft),
        },
        pickupPointDraft.work_time
            ? {
                  key: "work_time",
                  label: translate("delivery.pickupPointWorkTimeLabel"),
                  value: pickupPointDraft.work_time,
              }
            : null,
        pickupPointDraft.phones?.length
            ? {
                  key: "phones",
                  label: translate("delivery.pickupPointPhoneLabel"),
                  value: pickupPointDraft.phones.join(", "),
              }
            : null,
        pickupPointDraft.emails?.length
            ? {
                  key: "emails",
                  label: translate("delivery.pickupPointEmailLabel"),
                  value: pickupPointDraft.emails.join(", "),
              }
            : null,
    ]

    return rows.filter((row): row is DeliveryInfoRow => row !== null && Boolean(row.value))
}

export function arePointsClose(left: PointLike | null, right: PointLike | null, precision = 0.00005) {
    if (!left || !right) {
        return false
    }

    return (
        Math.abs(left.lat - right.lat) <= precision
        && Math.abs(left.lon - right.lon) <= precision
    )
}

export function areCameraPositionsEquivalent(
    left: CameraPosition | null,
    right: CameraPosition | null,
    precision = 0.00005,
) {
    if (!left || !right) {
        return false
    }

    return (
        arePointsClose(left.point, right.point, precision)
        && Math.abs(left.zoom - right.zoom) <= 0.01
        && Math.abs(left.azimuth - right.azimuth) <= 0.01
        && Math.abs(left.tilt - right.tilt) <= 0.01
        && left.reason === right.reason
        && left.finished === right.finished
    )
}

function getPointDistanceScore(left: Point, right: Point) {
    const latitudeDelta = left.lat - right.lat
    const averageLatitudeRadians = (((left.lat + right.lat) / 2) * Math.PI) / 180
    const longitudeDelta = (left.lon - right.lon) * Math.cos(averageLatitudeRadians)

    return latitudeDelta * latitudeDelta + longitudeDelta * longitudeDelta
}

export function getNearestPickupMarkers(markers: DeliveryMapMarker[], center: Point, limit: number) {
    if (markers.length <= limit) {
        return markers
    }

    return [...markers]
        .sort((left, right) => {
            return getPointDistanceScore(left.point, center) - getPointDistanceScore(right.point, center)
        })
        .slice(0, limit)
}
