import { COUNTRY_SELECTOR_CODES } from "@/components/country-flag/country-flag.consts"
import type { InitialRegion, Point } from "react-native-yamap"
import type {
    DeliveryCountryCode,
    DeliveryGeoBounds,
    DeliveryGeoCodeResult,
    DeliveryPointProvider,
} from "@/services/api/delivery.types"

const SUPPORTED_DELIVERY_COUNTRY_CODES = new Set<DeliveryCountryCode>(COUNTRY_SELECTOR_CODES)
const DOOR_DELIVERY_COUNTRY_CODES = new Set<DeliveryCountryCode>(["RU", "BY", "KZ"])

// Country bounds are hardcoded from the Natural Earth–derived dataset here:
// https://github.com/sandstrom/country-bounding-boxes
type DeliveryCountryViewport = {
    bounds: DeliveryGeoBounds | null
    region: InitialRegion
}

const DELIVERY_COUNTRY_BOUNDS: Record<DeliveryCountryCode, DeliveryGeoBounds> = {
    AE: createDeliveryBounds(51.58, 22.5, 56.4, 26.06),
    AM: createDeliveryBounds(43.58, 38.74, 46.51, 41.25),
    AZ: createDeliveryBounds(44.79, 38.27, 50.39, 41.86),
    BD: createDeliveryBounds(88.08, 20.67, 92.67, 26.45),
    BY: createDeliveryBounds(23.2, 51.32, 32.69, 56.17),
    CN: createDeliveryBounds(73.68, 18.2, 135.03, 53.46),
    GE: createDeliveryBounds(39.96, 41.06, 46.64, 43.55),
    ID: createDeliveryBounds(95.29, -10.36, 141.03, 5.48),
    IL: createDeliveryBounds(34.27, 29.5, 35.84, 33.28),
    IN: createDeliveryBounds(68.18, 7.97, 97.4, 35.49),
    JP: createDeliveryBounds(129.41, 31.03, 145.54, 45.55),
    KG: createDeliveryBounds(69.46, 39.28, 80.26, 43.3),
    KZ: createDeliveryBounds(46.47, 40.66, 87.36, 55.39),
    MD: createDeliveryBounds(26.62, 45.49, 30.02, 48.47),
    MN: createDeliveryBounds(87.75, 41.6, 119.77, 52.05),
    RS: createDeliveryBounds(18.83, 42.25, 22.99, 46.17),
    RU: createDeliveryBounds(-180, 41.15, 180, 81.25),
    TH: createDeliveryBounds(97.38, 5.69, 105.59, 20.42),
    US: createDeliveryBounds(-125, 25, -66.96, 49.5),
    UZ: createDeliveryBounds(55.93, 37.14, 73.06, 45.59),
    VN: createDeliveryBounds(102.17, 8.6, 109.34, 23.35),
}

const DELIVERY_COUNTRY_REGION_OVERRIDES: Partial<Record<DeliveryCountryCode, InitialRegion>> = {
    // Russia crosses the antimeridian in the source bounding box, so a region override
    // keeps the manual camera jump from zooming the whole world.
    RU: getDeliveryRegion(
        {
            lat: 61.2,
            lon: 105.0,
        },
        3,
    ),
}

const DOOR_DELIVERY_START_REGIONS: Partial<Record<DeliveryCountryCode, InitialRegion>> = {
    BY: getDeliveryRegion(
        {
            lat: 53.902284,
            lon: 27.561831,
        },
        16,
    ),
    KZ: getDeliveryRegion(
        {
            lat: 43.238949,
            lon: 76.889709,
        },
        16,
    ),
    RU: getDeliveryRegion(
        {
            lat: 55.751244,
            lon: 37.618423,
        },
        16,
    ),
}


export const DEFAULT_DELIVERY_POINT: Point = {
    lat: 55.751244,
    lon: 37.618423,
}

export const DOOR_DELIVERY_PROVIDER: DeliveryPointProvider = "cdek"
export const DEFAULT_DELIVERY_ZOOM = 12
export const PICKUP_POINT_FOCUS_ZOOM = 17
export const MAX_NATIVE_PICKUP_MARKERS = 80000
export const DOOR_DELIVERY_LOOKUP_DELAY_MS = 420
export const DELIVERY_CAMERA_DURATIONS = {
    country: 0.7,
    follow: 1.2,
    search: 0.55,
    startup: 0.8,
} as const
export const DELIVERY_CLUSTER_MARKER_ICONS = {
    cdek: require("@/assets/icons/delivery-services/cdek.png"),
    yandex: require("@/assets/icons/delivery-services/yandex.png"),
} as const

const DELIVERY_POINT_FOCUS_KINDS = new Set([
    "apartment",
    "entrance",
    "house",
    "level",
])

export function isPreciseDoorDeliverySelection(
    selection: Pick<DeliveryGeoCodeResult, "kind" | "precision">,
): boolean {
    return DELIVERY_POINT_FOCUS_KINDS.has(selection.kind) || selection.precision === "exact"
}

export function supportsDoorDeliveryForCountry(countryCode: DeliveryCountryCode | null | undefined): boolean {
    return countryCode ? DOOR_DELIVERY_COUNTRY_CODES.has(countryCode) : false
}

export function getDoorDeliveryStartRegion(countryCode: DeliveryCountryCode): InitialRegion {
    return DOOR_DELIVERY_START_REGIONS[countryCode] ?? getDeliveryCountryViewport(countryCode).region
}

const DELIVERY_KIND_ZOOM: Record<string, number> = {
    apartment: 18,
    country: 5,
    district: 12,
    entrance: 18,
    house: 16,
    locality: 10,
    metro_station: 15,
    province: 7,
    railway_station: 14,
    route: 10,
    station: 14,
    street: 14,
}

type DeliveryMapSelection = Pick<DeliveryGeoCodeResult, "bounds" | "kind" | "lat" | "lon">

export function getDeliveryCountryViewport(countryCode: DeliveryCountryCode): DeliveryCountryViewport {
    const bounds = DELIVERY_COUNTRY_BOUNDS[countryCode]
    const region =
        DELIVERY_COUNTRY_REGION_OVERRIDES[countryCode] ??
        getDeliveryRegion(getDeliveryBoundsCenter(bounds), getDeliveryZoomFromBounds(bounds))

    return {
        bounds: boundsCrossAntimeridian(bounds) ? null : bounds,
        region,
    }
}

export function getSupportedDeliveryCountryCode(countryCode: string | null | undefined): DeliveryCountryCode | null {
    const normalizedCountryCode = countryCode?.trim().toUpperCase()
    if (!normalizedCountryCode) {
        return null
    }

    return SUPPORTED_DELIVERY_COUNTRY_CODES.has(normalizedCountryCode as DeliveryCountryCode)
        ? (normalizedCountryCode as DeliveryCountryCode)
        : null
}

export function getDeliveryRegion(point: Point, zoom = DEFAULT_DELIVERY_ZOOM): InitialRegion {
    return {
        lat: point.lat,
        lon: point.lon,
        zoom,
        azimuth: 0,
        tilt: 0,
    }
}

export function shouldUseDeliveryBounds(selection: Pick<DeliveryGeoCodeResult, "bounds" | "kind">): boolean {
    return Boolean(selection.bounds) && !DELIVERY_POINT_FOCUS_KINDS.has(selection.kind)
}

export function getDeliveryBoundsCenter(bounds: DeliveryGeoBounds): Point {
    return {
        lat: (bounds.south_west.lat + bounds.north_east.lat) / 2,
        lon: (bounds.south_west.lon + bounds.north_east.lon) / 2,
    }
}

export function getDeliveryBoundsPoints(bounds: DeliveryGeoBounds): Point[] {
    return [
        {
            lat: bounds.south_west.lat,
            lon: bounds.south_west.lon,
        },
        {
            lat: bounds.north_east.lat,
            lon: bounds.north_east.lon,
        },
    ]
}

export function getDeliverySelectionCenter(selection: DeliveryMapSelection): Point {
    if (selection.bounds && shouldUseDeliveryBounds(selection)) {
        return getDeliveryBoundsCenter(selection.bounds)
    }

    return {
        lat: selection.lat,
        lon: selection.lon,
    }
}

export function getDeliverySelectionZoom(selection: Pick<DeliveryGeoCodeResult, "bounds" | "kind">): number {
    if (selection.bounds && shouldUseDeliveryBounds(selection)) {
        return getDeliveryZoomFromBounds(selection.bounds)
    }

    return DELIVERY_KIND_ZOOM[selection.kind] ?? DEFAULT_DELIVERY_ZOOM
}

export function getDeliverySelectionRegion(selection: DeliveryMapSelection): InitialRegion {
    return getDeliveryRegion(
        getDeliverySelectionCenter(selection),
        getDeliverySelectionZoom(selection),
    )
}

function getDeliveryZoomFromBounds(bounds: DeliveryGeoBounds): number {
    const latitudeSpan = Math.abs(bounds.north_east.lat - bounds.south_west.lat)
    const longitudeSpan = Math.abs(bounds.north_east.lon - bounds.south_west.lon)
    const span = Math.max(latitudeSpan, longitudeSpan)

    if (span >= 40) return 3
    if (span >= 20) return 4
    if (span >= 10) return 5
    if (span >= 5) return 6
    if (span >= 2) return 7
    if (span >= 1) return 8
    if (span >= 0.5) return 9
    if (span >= 0.2) return 10
    if (span >= 0.1) return 11
    if (span >= 0.05) return 12
    if (span >= 0.02) return 13
    if (span >= 0.01) return 14
    if (span >= 0.005) return 15
    return 16
}

function boundsCrossAntimeridian(bounds: DeliveryGeoBounds): boolean {
    return Math.abs(bounds.north_east.lon - bounds.south_west.lon) >= 180
}

function createDeliveryBounds(west: number, south: number, east: number, north: number): DeliveryGeoBounds {
    return {
        south_west: {
            lat: south,
            lon: west,
        },
        north_east: {
            lat: north,
            lon: east,
        },
    }
}

export const DEFAULT_DELIVERY_REGION = getDeliveryRegion(DEFAULT_DELIVERY_POINT)
