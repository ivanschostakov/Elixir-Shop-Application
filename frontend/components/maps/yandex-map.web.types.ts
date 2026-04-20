export type GeoPoint = {
    lat: number
    lon: number
}

export type YandexMapMarker = GeoPoint & {
    code?: string
    label?: string
    provider?: "cdek" | "yandex"
}

export type YandexMapWebProps = {
    center: GeoPoint
    marker?: YandexMapMarker
    markers?: YandexMapMarker[]
    zoom?: number
    markerLabel?: string
    onMapClick?: (point: GeoPoint) => void
    onMarkerClick?: (marker: YandexMapMarker) => void
}

export type YMapLocation = {
    center: [number, number]
    zoom: number
}

export type YMapInstance = {
    addChild: (child: unknown) => unknown
    destroy: () => void
    update?: (props: {
        location?: YMapLocation
    }) => unknown
}

export type YandexClusterFeature = {
    type: "Feature"
    id: string
    geometry: {
        type: "Point"
        coordinates: [number, number]
    }
    properties: {
        marker: YandexMapMarker
    }
}

export type YMaps3Import = {
    (packageName: string): Promise<{
        YMapClusterer: new (props: {
            method: unknown
            features: YandexClusterFeature[]
            marker: (feature: YandexClusterFeature) => unknown
            cluster: (coordinates: [number, number], features: YandexClusterFeature[]) => unknown
        }) => unknown
        clusterByGrid: (props: {
            gridSize: number
        }) => unknown
    }>
    registerCdn: (urlMask: string, packages: string | string[]) => void
}

export type YMaps3Global = {
    ready: Promise<void>
    import: YMaps3Import
    YMap: new (
        container: HTMLElement,
        options: {
            location: YMapLocation
        }
    ) => YMapInstance
    YMapDefaultSchemeLayer: new (props?: Record<string, unknown>) => unknown
    YMapDefaultFeaturesLayer: new (props?: Record<string, unknown>) => unknown
    YMapFeatureDataSource: new (props: {
        id: string
    }) => unknown
    YMapLayer: new (props: {
        source: string
        type: "markers" | "features" | "tiles"
        zIndex?: number
    }) => unknown
    YMapMarker: new (
        props: {
            coordinates: [number, number]
            source?: string
        },
        element: HTMLElement
    ) => unknown
    YMapListener: new (props: {
        layer?: string
        onClick?: (
            object: {
                entity?: unknown
                type?: string
            } | undefined,
            event: {
                coordinates: [number, number]
                screenCoordinates?: [number, number]
            },
        ) => void
    }) => unknown
}

declare global {
    interface Window {
        ymaps3?: YMaps3Global
        __ymaps3ScriptPromise?: Promise<void>
        __ymaps3ClustererRegistered?: boolean
    }
}
