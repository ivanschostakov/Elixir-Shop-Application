import {
    CDEK_PICKUP_MARKER_INNER_BORDER_COLOR,
    CDEK_PICKUP_MARKER_INNER_COLOR,
    CDEK_PICKUP_MARKER_INNER_SIZE,
    CDEK_PICKUP_MARKER_OUTER_COLOR,
    CDEK_PICKUP_MARKER_OUTER_SIZE,
    CDEK_PICKUP_MARKER_SHADOW,
    CDEK_PICKUP_MARKER_TEXT,
    CDEK_PICKUP_MARKER_TEXT_COLOR,
    YANDEX_PICKUP_MARKER_INNER_COLOR,
    YANDEX_PICKUP_MARKER_TEXT,
} from "@/components/maps/cdek-pickup-marker.constants"
import type {
    GeoPoint,
    YMapInstance,
    YandexClusterFeature,
    YandexMapMarker,
    YMaps3Global,
} from "@/components/maps/yandex-map.web.types"

export const YANDEX_MAP_MARKER_SOURCE = "delivery-markers"
const YANDEX_CLUSTERER_CDN_URL = "https://cdn.jsdelivr.net/npm/{package}"
const YANDEX_CLUSTERER_PACKAGE = "@yandex/ymaps3-clusterer"
const YANDEX_CLUSTERER_CDN_PACKAGE = `${YANDEX_CLUSTERER_PACKAGE}@0.0.11`

export function loadYandexMapsScript(apiKey: string): Promise<void> {
    if (typeof window === "undefined") {
        return Promise.reject(new Error("Window is not available."))
    }

    if (window.ymaps3) {
        return Promise.resolve()
    }

    if (window.__ymaps3ScriptPromise) {
        return window.__ymaps3ScriptPromise
    }

    window.__ymaps3ScriptPromise = new Promise((resolve, reject) => {
        const script = document.createElement("script")

        script.src = `https://api-maps.yandex.ru/v3/?apikey=${encodeURIComponent(apiKey)}&lang=en_US`
        script.async = true
        script.onload = () => resolve()
        script.onerror = () => {
            window.__ymaps3ScriptPromise = undefined
            reject(new Error("Failed to load Yandex Maps JS API script."))
        }
        document.head.appendChild(script)
    })

    return window.__ymaps3ScriptPromise
}

function createPickupMarkerElement(
    label: string,
    provider: YandexMapMarker["provider"] = "cdek",
): HTMLElement {
    const markerElement = document.createElement("div")
    markerElement.style.width = `${CDEK_PICKUP_MARKER_OUTER_SIZE}px`
    markerElement.style.height = `${CDEK_PICKUP_MARKER_OUTER_SIZE}px`
    markerElement.style.borderRadius = "999px"
    markerElement.style.background = CDEK_PICKUP_MARKER_OUTER_COLOR
    markerElement.style.display = "flex"
    markerElement.style.alignItems = "center"
    markerElement.style.justifyContent = "center"
    markerElement.style.boxShadow = CDEK_PICKUP_MARKER_SHADOW
    markerElement.title = label

    const innerCircle = document.createElement("div")
    innerCircle.style.width = `${CDEK_PICKUP_MARKER_INNER_SIZE}px`
    innerCircle.style.height = `${CDEK_PICKUP_MARKER_INNER_SIZE}px`
    innerCircle.style.borderRadius = "999px"
    innerCircle.style.display = "flex"
    innerCircle.style.alignItems = "center"
    innerCircle.style.justifyContent = "center"
    innerCircle.style.background =
        provider === "yandex" ? YANDEX_PICKUP_MARKER_INNER_COLOR : CDEK_PICKUP_MARKER_INNER_COLOR
    innerCircle.style.border = `2px solid ${CDEK_PICKUP_MARKER_INNER_BORDER_COLOR}`

    const text = document.createElement("span")
    text.textContent = provider === "yandex" ? YANDEX_PICKUP_MARKER_TEXT : CDEK_PICKUP_MARKER_TEXT
    text.style.color = CDEK_PICKUP_MARKER_TEXT_COLOR
    text.style.fontSize = provider === "yandex" ? "10px" : "9px"
    text.style.fontStyle = provider === "yandex" ? "normal" : "italic"
    text.style.fontWeight = "900"
    text.style.letterSpacing = provider === "yandex" ? "0" : "-0.5px"
    text.style.lineHeight = "10px"
    text.style.fontFamily = "Arial, sans-serif"

    innerCircle.appendChild(text)
    markerElement.appendChild(innerCircle)

    return markerElement
}

export function createMarkerElement(
    marker: YandexMapMarker,
    fallbackLabel: string,
    onClick?: (marker: YandexMapMarker) => void,
): HTMLElement {
    const label = marker.label ?? fallbackLabel
    const markerElement = createPickupMarkerElement(label, marker.provider)

    if (onClick) {
        markerElement.style.cursor = "pointer"
        markerElement.tabIndex = 0
        markerElement.setAttribute("role", "button")

        const handleActivate = (event: Event) => {
            event.preventDefault()
            event.stopPropagation()
            onClick(marker)
        }

        markerElement.addEventListener("click", handleActivate)
        markerElement.addEventListener("keydown", (event) => {
            if (!(event instanceof KeyboardEvent) || (event.key !== "Enter" && event.key !== " ")) {
                return
            }

            handleActivate(event)
        })
    }

    return markerElement
}

export function createClusterElement(count: number): HTMLElement {
    const clusterElement = document.createElement("div")
    clusterElement.style.minWidth = "42px"
    clusterElement.style.height = "42px"
    clusterElement.style.padding = "0 14px"
    clusterElement.style.borderRadius = "999px"
    clusterElement.style.display = "flex"
    clusterElement.style.alignItems = "center"
    clusterElement.style.justifyContent = "center"
    clusterElement.style.boxSizing = "border-box"
    clusterElement.style.background = CDEK_PICKUP_MARKER_OUTER_COLOR
    clusterElement.style.border = "2px solid rgba(255, 255, 255, 0.95)"
    clusterElement.style.boxShadow = "0 10px 24px rgba(0, 65, 120, 0.22)"
    clusterElement.style.color = "#FFFFFF"
    clusterElement.style.fontSize = "17px"
    clusterElement.style.fontWeight = "600"
    clusterElement.style.fontFamily =
        "\"SF Pro Display\", \"Segoe UI\", Inter, system-ui, -apple-system, BlinkMacSystemFont, sans-serif"
    clusterElement.style.lineHeight = "1"
    clusterElement.textContent = String(count)
    clusterElement.setAttribute("aria-label", `${count} delivery points`)

    return clusterElement
}

export function registerYandexClustererPackage(ymaps3: YMaps3Global) {
    if (window.__ymaps3ClustererRegistered) {
        return
    }

    ymaps3.import.registerCdn(YANDEX_CLUSTERER_CDN_URL, YANDEX_CLUSTERER_CDN_PACKAGE)
    window.__ymaps3ClustererRegistered = true
}

export function toYandexClusterFeature(marker: YandexMapMarker, index: number): YandexClusterFeature {
    return {
        type: "Feature",
        id: `delivery-cluster-marker-${index}-${marker.lon}-${marker.lat}`,
        geometry: {
            type: "Point",
            coordinates: toYandexCoordinates(marker),
        },
        properties: {
            marker,
        },
    }
}

export function resetMapInstance(mapRef: { current: YMapInstance | null }) {
    mapRef.current?.destroy()
    mapRef.current = null
}

export function fromYandexCoordinates(point: [number, number]): GeoPoint {
    return {
        lat: point[1],
        lon: point[0],
    }
}

export function toYandexCoordinates(point: GeoPoint): [number, number] {
    return [point.lon, point.lat]
}
