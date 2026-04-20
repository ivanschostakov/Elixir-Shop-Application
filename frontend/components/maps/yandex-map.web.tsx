import { useEffect, useMemo, useRef, useState } from "react"
import {
    DEFAULT_MARKER_LABEL,
    DEFAULT_YANDEX_MAP_ZOOM,
    FULLSCREEN_BUTTON_LABEL,
    YANDEX_MAPS_API_KEY,
} from "@/components/maps/yandex-map.web.const"
import { yandexMapWebStyles } from "@/components/maps/yandex-map.web.styles"
import type { YMapInstance, YandexMapWebProps } from "@/components/maps/yandex-map.web.types"
import {
    createClusterElement,
    createMarkerElement,
    fromYandexCoordinates,
    loadYandexMapsScript,
    registerYandexClustererPackage,
    resetMapInstance,
    toYandexClusterFeature,
    toYandexCoordinates,
    YANDEX_MAP_MARKER_SOURCE,
} from "@/components/maps/yandex-map.web.utils"

export function YandexMapWeb({
    center,
    marker,
    markers,
    zoom = DEFAULT_YANDEX_MAP_ZOOM,
    markerLabel = DEFAULT_MARKER_LABEL,
    onMapClick,
    onMarkerClick,
}: YandexMapWebProps) {
    const mapContainerRef = useRef<HTMLDivElement | null>(null)
    const mapRef = useRef<YMapInstance | null>(null)
    const latestLocationRef = useRef({
        center,
        zoom,
    })
    const latestCallbacksRef = useRef({
        onMapClick,
        onMarkerClick,
    })
    const [error, setError] = useState<string | null>(null)
    const apiKey = YANDEX_MAPS_API_KEY
    const mapMarkers = useMemo(() => {
        if (markers && markers.length > 0) {
            return markers
        }

        return marker ? [marker] : []
    }, [marker, markers])

    useEffect(() => {
        latestCallbacksRef.current = {
            onMapClick,
            onMarkerClick,
        }
    }, [onMapClick, onMarkerClick])

    useEffect(() => {
        latestLocationRef.current = {
            center,
            zoom,
        }

        mapRef.current?.update?.({
            location: {
                center: toYandexCoordinates(center),
                zoom,
            },
        })
    }, [center, zoom])

    useEffect(() => {
        let isCancelled = false

        async function initMap() {
            if (!mapContainerRef.current) {
                return
            }

            try {
                setError(null)

                await loadYandexMapsScript(apiKey)
                if (isCancelled) {
                    return
                }

                const ymaps3 = window.ymaps3
                if (!ymaps3) {
                    throw new Error("Yandex Maps API did not initialize.")
                }

                await ymaps3.ready
                if (isCancelled || !mapContainerRef.current) {
                    return
                }

                registerYandexClustererPackage(ymaps3)
                resetMapInstance(mapRef)

                const location = latestLocationRef.current
                const nextMap = new ymaps3.YMap(mapContainerRef.current, {
                    location: {
                        center: toYandexCoordinates(location.center),
                        zoom: location.zoom,
                    },
                })

                nextMap.addChild(new ymaps3.YMapDefaultSchemeLayer({}))
                nextMap.addChild(new ymaps3.YMapDefaultFeaturesLayer({}))
                nextMap.addChild(
                    new ymaps3.YMapListener({
                        layer: "any",
                        onClick: (object, event) => {
                            if (object) {
                                return
                            }

                            latestCallbacksRef.current.onMapClick?.(
                                fromYandexCoordinates(event.coordinates),
                            )
                        },
                    })
                )
                nextMap.addChild(
                    new ymaps3.YMapFeatureDataSource({
                        id: YANDEX_MAP_MARKER_SOURCE,
                    })
                )
                nextMap.addChild(
                    new ymaps3.YMapLayer({
                        source: YANDEX_MAP_MARKER_SOURCE,
                        type: "markers",
                        zIndex: 2000,
                    })
                )
                mapRef.current = nextMap

                if (mapMarkers.length > 0) {
                    const { YMapClusterer, clusterByGrid } = await ymaps3.import("@yandex/ymaps3-clusterer")
                    if (isCancelled) {
                        resetMapInstance(mapRef)
                        return
                    }

                    const clusterer = new YMapClusterer({
                        method: clusterByGrid({ gridSize: 64 }),
                        features: mapMarkers.map(toYandexClusterFeature),
                        marker: (feature) =>
                            new ymaps3.YMapMarker(
                                {
                                    coordinates: feature.geometry.coordinates,
                                    source: YANDEX_MAP_MARKER_SOURCE,
                                },
                                createMarkerElement(
                                    feature.properties.marker,
                                    markerLabel,
                                    (clickedMarker) => {
                                        latestCallbacksRef.current.onMarkerClick?.(clickedMarker)
                                    },
                                )
                            ),
                        cluster: (coordinates, features) =>
                            new ymaps3.YMapMarker(
                                {
                                    coordinates,
                                    source: YANDEX_MAP_MARKER_SOURCE,
                                },
                                createClusterElement(features.length)
                            ),
                    })

                    nextMap.addChild(clusterer)
                }
            } catch (initError) {
                const message = initError instanceof Error ? initError.message : "Failed to initialize map."
                setError(message)
            }
        }

        void initMap()

        return () => {
            isCancelled = true
            resetMapInstance(mapRef)
        }
    }, [apiKey, mapMarkers, markerLabel])

    function handleFullscreen() {
        if (!mapContainerRef.current) {
            return
        }

        if (document.fullscreenElement) {
            void document.exitFullscreen()
            return
        }

        void mapContainerRef.current.requestFullscreen()
    }

    return (
        <div style={yandexMapWebStyles.root}>
            <div ref={mapContainerRef} style={yandexMapWebStyles.map} />
            <button onClick={handleFullscreen} style={yandexMapWebStyles.fullscreenButton} type="button">
                {FULLSCREEN_BUTTON_LABEL}
            </button>
            {error ? <div style={yandexMapWebStyles.errorBanner}>{error}</div> : null}
        </div>
    )
}
