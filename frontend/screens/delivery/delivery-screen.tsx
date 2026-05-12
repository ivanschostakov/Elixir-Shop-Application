import { BlurView } from "expo-blur"
import * as Clipboard from "expo-clipboard"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
    ActivityIndicator,
    Alert,
    Animated,
    AppState,
    Easing,
    InteractionManager,
    Keyboard,
    KeyboardAvoidingView,
    Linking,
    Platform,
    Pressable,
    ScrollView,
    StyleSheet,
    Text,
    View,
    type AppStateStatus,
    type LayoutChangeEvent,
    type NativeSyntheticEvent,
} from "react-native"
import { useLocalSearchParams, useRouter } from "expo-router"
import { useSafeAreaInsets } from "react-native-safe-area-context"
import {
    ClusteredYamap,
    type CameraPosition,
    type MapLoaded,
    type Point,
} from "react-native-yamap"

import { DeliveryCornerButton } from "@/components/delivery/delivery-corner-button"
import { PickupPointFooterExtension } from "@/components/delivery/pickup-point-footer-extension"
import { DeliverySearchPanel } from "@/components/delivery/delivery-search-panel"
import { CountryFlag } from "@/components/country-flag/country-flag"
import { COUNTRY_SELECTOR_CODES } from "@/components/country-flag/country-flag.consts"
import { EdgeBlur } from "@/components/effects/edge-blur"
import { StickyFooterSurface } from "@/components/footer/sticky-footer"
import { BACK_ARROW_PATH, MY_LOCATION_ICON_PATH } from "@/components/header/app-header.constants"
import { CDEK_PICKUP_MARKER_OUTER_COLOR } from "@/components/maps/cdek-pickup-marker.constants"
import { DeliveryPlaceMarker } from "@/components/maps/delivery-place-marker"
import { MapFlowTemplate } from "@/components/templates/map-flow-template"
import { ROUTES } from "@/constants/routes"
import { setBasketSnapshot } from "@/hooks/basket/basket-store"
import {
    setSelectedDeliveryAddress,
    useSelectedDeliveryAddress,
} from "@/hooks/delivery/delivery-address-selection-store"
import {
    setSelectedDeliveryCountry,
    useSelectedDeliveryCountry,
} from "@/hooks/delivery/delivery-country-selection-store"
import {
    setSelectedDeliveryPoint,
    useSelectedDeliveryPoint,
} from "@/hooks/delivery/delivery-point-selection-store"
import { setOrderDraftSnapshot } from "@/hooks/order-draft/order-draft-store"
import { useDeliveryPointMarkers } from "@/hooks/delivery/use-delivery-point-markers"
import { translate } from "@/i18n/translations"
import { logDeliveryFlow } from "@/services/diagnostics/delivery-flow-logger"
import {
    calculateCdekDelivery,
    calculateYandexDelivery,
    geocodeDeliveryAddress,
    getCdekDeliveryPoint,
    getYandexDeliveryPoint,
    reverseGeocodeDeliveryPoint,
} from "@/services/api/delivery"
import { ApiError } from "@/services/api/client"
import type {
    DeliveryGeoCodeResult,
    DeliveryGeoSuggestResult,
    DeliveryPointProvider,
} from "@/services/api/delivery.types"
import { updateBasketCheckout } from "@/services/api/basket"
import { updateOrderDraft } from "@/services/api/order-drafts"
import { initializeYandexMapKit } from "@/services/maps/yandex-mapkit"
import {
    DOOR_DELIVERY_PROVIDER,
    DELIVERY_CAMERA_DURATIONS,
    DEFAULT_DELIVERY_REGION,
    DELIVERY_CLUSTER_MARKER_ICONS,
    DOOR_DELIVERY_LOOKUP_DELAY_MS,
    MAX_NATIVE_PICKUP_MARKERS,
    PICKUP_POINT_FOCUS_ZOOM,
    getDeliveryCountryViewport,
    getDeliveryRegion,
    getDeliverySelectionRegion,
    getSupportedDeliveryCountryCode,
    supportsDoorDeliveryForCountry,
} from "@/screens/delivery/delivery-screen.constants"
import {
    calculateDoorDelivery,
    getDeliveryActionLabel,
    getPickupPointActionLabel,
} from "@/screens/delivery/delivery-calculation"
import { useDeliveryLocation, useDeliveryMapCamera } from "@/screens/delivery/delivery-screen.hooks"
import { deliveryScreenStyles } from "@/screens/delivery/delivery-screen.styles"
import { useDeliveryFlowController } from "@/screens/delivery/use-delivery-flow-controller"
import type { DeliveryMapMarker } from "@/screens/delivery/delivery-screen.types"
import {
    arePointsClose,
    buildCdekPickupCalculationRequest,
    buildDoorDeliveryDraft,
    buildDoorOrderDraftPayload,
    buildOrderDraftAddressUpdatePayload,
    buildPickupOrderDraftPayload,
    buildPickupPointDraft,
    getClusteredMarkerPayload,
    getDeliveryCalculationErrorMessage,
    getDeliveryPointMarkerKey,
    getDoorDeliveryInfoRows,
    getPickupPointAddress,
    getPickupPointInfoRows,
    parseBooleanSearchParam,
    parseDraftId,
} from "@/screens/delivery/delivery-screen.utils"
import { colors } from "@/theme/colors"
import { spacing } from "@/theme/spacing"
import { showBackendErrorAlert } from "@/utils/errors"

type MapKitStatus = "loading" | "ready" | "error"

const DELIVERY_FLOW_LOG_PREFIX = "[delivery-flow]"

const getDeliveryLogErrorMessage = (error: unknown) =>
    error instanceof Error ? error.message : "Unknown delivery flow error"

export default function DeliveryScreen() {
    const router = useRouter()
    const params = useLocalSearchParams<{ draftId?: string | string[]; syncBasket?: string | string[] }>()
    const checkoutDraftId = parseDraftId(params.draftId)
    const shouldSyncBasketItems = parseBooleanSearchParam(params.syncBasket)
    const insets = useSafeAreaInsets()
    const mapRef = useRef<ClusteredYamap | null>(null)
    const pendingDeliveryPointCodeRef = useRef<string | null>(null)
    const pendingDoorResolutionTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const nativeMapMountInteractionRef = useRef<{ cancel: () => void } | null>(null)
    const nativeMapMountTokenRef = useRef(0)
    const lastFollowedUserPointRef = useRef<Point | null>(null)
    const cameraPositionRef = useRef<CameraPosition | null>(null)
    const lastDeliveryAppStateRef = useRef<AppStateStatus>(AppState.currentState)
    const [hasMovedDoorDeliveryMapOnce, setHasMovedDoorDeliveryMapOnce] = useState(false)
    const [isDoorDeliveryMapInteracting, setIsDoorDeliveryMapInteracting] = useState(false)
    const selectedDeliveryAddress = useSelectedDeliveryAddress()
    const selectedDeliveryPoint = useSelectedDeliveryPoint()
    const selectedDeliveryCountry = useSelectedDeliveryCountry()
    const [mapKitStatus, setMapKitStatus] = useState<MapKitStatus>("loading")
    const [shouldRenderNativeMap, setShouldRenderNativeMap] = useState(false)
    const [hasNativeMapLoaded, setHasNativeMapLoaded] = useState(false)
    const [shouldLoadPickupMarkers, setShouldLoadPickupMarkers] = useState(false)
    const {
        hasUserLocation,
        requestUserLocation,
        userPoint,
    } = useDeliveryLocation()
    const { handleMapLoaded, moveToRegion } = useDeliveryMapCamera(mapRef)
    const {
        activeCountryCode,
        clearResults,
        doorDeliveryDraft,
        doorDeliveryPoint,
        error,
        hasVisibleSearchFeedback,
        isDoorFooterExpanded,
        isLoading,
        isResolvingDoorAddress,
        isResolvingPickupPoint,
        isSearchActive,
        pickupPoint,
        pickupPointDraft,
        pickupPointError,
        removedDeliveryPointKeys,
        results,
        runSearch,
        search,
        searchFocusPoint,
        selectionError,
        setDoorDeliveryDraft,
        setIsDoorFooterExpanded,
        setIsPickupFooterExpanded,
        setIsResolvingDoorAddress,
        setIsResolvingPickupPoint,
        setIsSearchFocused,
        setPickupPointDraft,
        setPickupPointError,
        setRemovedDeliveryPointKeys,
        setSearch,
        setSearchEnabled,
        setSearchFocusPoint,
        setSelectionError,
        shouldShowDoorFooterExtension,
        shouldShowPickupFooterExtension,
        supportsDoorDelivery,
    } = useDeliveryFlowController({
        selectedDeliveryAddress,
        selectedDeliveryCountry,
        selectedDeliveryPoint,
        userPoint,
    })
    const activeCountryCodeRef = useRef(activeCountryCode)
    const deliveryScreenMountLogContextRef = useRef({
        activeCountryCode,
        checkoutDraftId,
        hasSelectedDeliveryAddress: Boolean(selectedDeliveryAddress),
        hasSelectedDeliveryPoint: Boolean(selectedDeliveryPoint),
        selectedDeliveryCountry,
        shouldSyncBasketItems,
    })
    const {
        deliveryPointMarkers,
        error: deliveryPointsError,
        isLoading: isDeliveryPointsLoading,
    } = useDeliveryPointMarkers(activeCountryCode, {
        enabled: shouldLoadPickupMarkers,
    })
    const isMapKitReady = mapKitStatus === "ready"
    const shouldBlockPickupMarkers =
        isMapKitReady
        && !deliveryPointsError
        && (!shouldLoadPickupMarkers || isDeliveryPointsLoading)
    const shouldRenderMap = isMapKitReady && shouldRenderNativeMap
    const shouldFollowUser =
        hasUserLocation
        && selectedDeliveryCountry === null
        && searchFocusPoint === null
        && doorDeliveryPoint === null
        && pickupPoint === null
    const shouldShowDoorDeliveryMarker =
        isMapKitReady
        && supportsDoorDelivery
        && !hasVisibleSearchFeedback
        && !shouldShowPickupFooterExtension
        && isDoorFooterExpanded
        && Boolean(isResolvingDoorAddress || doorDeliveryDraft)
    const shouldHideDoorDeliveryChrome = isDoorDeliveryMapInteracting
    const topMapEdgeBlurHeight = Math.max(insets.top, 0)
    const bottomMapEdgeBlurHeight = Math.max(insets.bottom + 28, 20)
    const doorChromeOpacity = useRef(new Animated.Value(1)).current
    const doorTopControlsTranslateY = useRef(new Animated.Value(0)).current
    const doorBottomControlsTranslateY = useRef(new Animated.Value(0)).current
    const initialMapRegion = useMemo(() => {
        if (selectedDeliveryCountry !== null) {
            return getDeliveryCountryViewport(selectedDeliveryCountry).region
        }

        if (hasUserLocation) {
            return getDeliveryRegion(userPoint)
        }

        return DEFAULT_DELIVERY_REGION
    }, [hasUserLocation, selectedDeliveryCountry, userPoint])

    const pickupMarkers = useMemo<DeliveryMapMarker[]>(
        () =>
            deliveryPointMarkers
                .filter((deliveryPointMarker) =>
                    !removedDeliveryPointKeys.has(
                        getDeliveryPointMarkerKey(
                            deliveryPointMarker.provider,
                            deliveryPointMarker.code,
                        ),
                    ),
                )
                .map((deliveryPointMarker) => ({
                iconKey: deliveryPointMarker.provider,
                point: {
                    lat: deliveryPointMarker.latitude,
                    lon: deliveryPointMarker.longitude,
                },
                data: {
                    code: deliveryPointMarker.code,
                    kind: "pickup",
                    provider: deliveryPointMarker.provider,
                },
            })),
        [deliveryPointMarkers, removedDeliveryPointKeys],
    )
    const mapMarkers = useMemo(
        () =>
            pickupMarkers.length > MAX_NATIVE_PICKUP_MARKERS
                ? pickupMarkers.slice(0, MAX_NATIVE_PICKUP_MARKERS)
                : pickupMarkers,
        [pickupMarkers],
    )
    const handleDeliveryMapLoaded = useCallback((event: NativeSyntheticEvent<MapLoaded>) => {
        logDeliveryFlow("delivery map loaded", {
            countryCode: activeCountryCode,
            hasNativeMapLoaded,
            markerSourceCount: deliveryPointMarkers.length,
            nativeStats: event.nativeEvent,
            pickupMarkerCount: pickupMarkers.length,
            shouldRenderNativeMap,
            shouldLoadPickupMarkers,
            visibleMarkerCount: mapMarkers.length,
        })
        setHasNativeMapLoaded(true)
        handleMapLoaded()
    }, [
        activeCountryCode,
        deliveryPointMarkers.length,
        hasNativeMapLoaded,
        handleMapLoaded,
        mapMarkers.length,
        pickupMarkers.length,
        shouldRenderNativeMap,
        shouldLoadPickupMarkers,
    ])
    const handleDeliveryMapLayout = useCallback((event: LayoutChangeEvent) => {
        const { height, width, x, y } = event.nativeEvent.layout
        logDeliveryFlow("delivery map layout measured", {
            countryCode: activeCountryCode,
            hasNativeMapLoaded,
            height,
            mapKitStatus,
            shouldRenderNativeMap,
            shouldRenderMap,
            visibleMarkerCount: mapMarkers.length,
            width,
            x,
            y,
        })
    }, [
        activeCountryCode,
        hasNativeMapLoaded,
        mapKitStatus,
        mapMarkers.length,
        shouldRenderMap,
        shouldRenderNativeMap,
    ])

    const clearPendingDoorResolution = useCallback(() => {
        if (!pendingDoorResolutionTimeoutRef.current) {
            return
        }

        clearTimeout(pendingDoorResolutionTimeoutRef.current)
        pendingDoorResolutionTimeoutRef.current = null
    }, [])

    useEffect(() => {
        const context = deliveryScreenMountLogContextRef.current
        logDeliveryFlow("delivery screen mounted", context)

        return () => {
            logDeliveryFlow("delivery screen unmounted", context)
        }
    }, [])

    useEffect(() => {
        activeCountryCodeRef.current = activeCountryCode
    }, [activeCountryCode])

    useEffect(() => {
        const subscription = AppState.addEventListener("change", (nextAppState) => {
            logDeliveryFlow("delivery app state changed", {
                countryCode: activeCountryCode,
                draftId: checkoutDraftId,
                from: lastDeliveryAppStateRef.current,
                hasNativeMapLoaded,
                isDeliveryPointsLoading,
                mapKitStatus,
                markerSourceCount: deliveryPointMarkers.length,
                shouldBlockPickupMarkers,
                shouldLoadPickupMarkers,
                shouldRenderNativeMap,
                to: nextAppState,
                visibleMarkerCount: mapMarkers.length,
            })
            lastDeliveryAppStateRef.current = nextAppState
        })

        return () => {
            subscription.remove()
        }
    }, [
        activeCountryCode,
        checkoutDraftId,
        deliveryPointMarkers.length,
        hasNativeMapLoaded,
        isDeliveryPointsLoading,
        mapKitStatus,
        mapMarkers.length,
        shouldBlockPickupMarkers,
        shouldLoadPickupMarkers,
        shouldRenderNativeMap,
    ])

    useEffect(() => {
        let isMounted = true

        logDeliveryFlow("mapkit initialization started")
        initializeYandexMapKit()
            .then(() => {
                if (isMounted) {
                    logDeliveryFlow("mapkit initialization ready")
                    setMapKitStatus("ready")
                } else {
                    logDeliveryFlow("mapkit initialization ready after unmount")
                }
            })
            .catch((mapKitError) => {
                logDeliveryFlow("mapkit initialization failed", {
                    error: getDeliveryLogErrorMessage(mapKitError),
                })
                console.error(`${DELIVERY_FLOW_LOG_PREFIX} mapkit initialization failed`, {
                    error: getDeliveryLogErrorMessage(mapKitError),
                })

                if (isMounted) {
                    setMapKitStatus("error")
                }
            })

        return () => {
            isMounted = false
        }
    }, [])

    useEffect(() => {
        nativeMapMountTokenRef.current += 1
        const mountToken = nativeMapMountTokenRef.current
        const countryCodeAtMount = activeCountryCodeRef.current

        nativeMapMountInteractionRef.current?.cancel()
        nativeMapMountInteractionRef.current = null
        setShouldRenderNativeMap(false)
        setHasNativeMapLoaded(false)

        if (!isMapKitReady) {
            logDeliveryFlow("delivery native map mount waiting for mapkit", {
                countryCode: countryCodeAtMount,
                mapKitStatus,
            })
            return
        }

        const delayMs = Platform.OS === "ios" ? 700 : 250
        logDeliveryFlow("delivery native map mount scheduled", {
            countryCode: countryCodeAtMount,
            delayMs,
        })

        const mountTimeout = setTimeout(() => {
            logDeliveryFlow("delivery native map mount waiting for interactions", {
                countryCode: countryCodeAtMount,
                token: mountToken,
            })

            nativeMapMountInteractionRef.current = InteractionManager.runAfterInteractions(() => {
                nativeMapMountInteractionRef.current = null

                if (nativeMapMountTokenRef.current !== mountToken) {
                    logDeliveryFlow("delivery native map mount skipped stale", {
                        countryCode: countryCodeAtMount,
                        latestToken: nativeMapMountTokenRef.current,
                        token: mountToken,
                    })
                    return
                }

                logDeliveryFlow("delivery native map mount enabled", {
                    countryCode: countryCodeAtMount,
                    token: mountToken,
                })
                setShouldRenderNativeMap(true)
            })
        }, delayMs)

        return () => {
            logDeliveryFlow("delivery native map mount cancelled", {
                countryCode: countryCodeAtMount,
                token: mountToken,
            })
            clearTimeout(mountTimeout)
            nativeMapMountInteractionRef.current?.cancel()
            nativeMapMountInteractionRef.current = null
        }
    }, [isMapKitReady, mapKitStatus])

    useEffect(() => {
        setRemovedDeliveryPointKeys(new Set())
    }, [activeCountryCode])

    useEffect(() => {
        if (!shouldRenderNativeMap || hasNativeMapLoaded) {
            return
        }

        const fallbackDelayMs = 4500
        logDeliveryFlow("delivery native map load fallback scheduled", {
            countryCode: activeCountryCode,
            fallbackDelayMs,
        })

        const fallbackTimeout = setTimeout(() => {
            logDeliveryFlow("delivery native map load fallback elapsed", {
                countryCode: activeCountryCode,
                fallbackDelayMs,
            })
            setHasNativeMapLoaded(true)
        }, fallbackDelayMs)

        return () => {
            logDeliveryFlow("delivery native map load fallback cancelled", {
                countryCode: activeCountryCode,
            })
            clearTimeout(fallbackTimeout)
        }
    }, [activeCountryCode, hasNativeMapLoaded, shouldRenderNativeMap])

    useEffect(() => {
        logDeliveryFlow("pickup marker gate reset", {
            countryCode: activeCountryCode,
            hasNativeMapLoaded,
            mapKitStatus,
            shouldRenderNativeMap,
        })
        setShouldLoadPickupMarkers(false)

        if (!isMapKitReady) {
            logDeliveryFlow("pickup marker gate waiting for mapkit", {
                countryCode: activeCountryCode,
                mapKitStatus,
            })
            return
        }

        if (!shouldRenderNativeMap) {
            logDeliveryFlow("pickup marker gate waiting for native map mount", {
                countryCode: activeCountryCode,
                mapKitStatus,
            })
            return
        }

        if (!hasNativeMapLoaded) {
            logDeliveryFlow("pickup marker gate waiting for native map loaded", {
                countryCode: activeCountryCode,
                mapKitStatus,
            })
            return
        }

        logDeliveryFlow("pickup marker load scheduled", {
            countryCode: activeCountryCode,
            delayMs: 250,
        })
        const markerLoadTimeout = setTimeout(() => {
            logDeliveryFlow("pickup marker load enabled", {
                countryCode: activeCountryCode,
            })
            setShouldLoadPickupMarkers(true)
        }, 250)

        return () => {
            logDeliveryFlow("pickup marker load schedule cancelled", {
                countryCode: activeCountryCode,
            })
            clearTimeout(markerLoadTimeout)
        }
    }, [
        activeCountryCode,
        hasNativeMapLoaded,
        isMapKitReady,
        mapKitStatus,
        shouldRenderNativeMap,
    ])

    useEffect(() => {
        const providerCounts = pickupMarkers.reduce<Record<string, number>>((counts, marker) => {
            const provider = "provider" in marker.data ? marker.data.provider : "unknown"
            counts[provider] = (counts[provider] ?? 0) + 1
            return counts
        }, {})

        logDeliveryFlow("pickup marker render state", {
            countryCode: activeCountryCode,
            hasError: Boolean(deliveryPointsError),
            hasNativeMapLoaded,
            isLoading: isDeliveryPointsLoading,
            markerSourceCount: deliveryPointMarkers.length,
            pickupMarkerCount: pickupMarkers.length,
            providerCounts,
            shouldBlockPickupMarkers,
            shouldLoadPickupMarkers,
            shouldRenderNativeMap,
            visibleMarkerCount: mapMarkers.length,
            visibleMarkersCapped: pickupMarkers.length > mapMarkers.length,
        })
    }, [
        activeCountryCode,
        deliveryPointMarkers.length,
        deliveryPointsError,
        hasNativeMapLoaded,
        isDeliveryPointsLoading,
        mapMarkers.length,
        pickupMarkers,
        pickupMarkers.length,
        shouldBlockPickupMarkers,
        shouldLoadPickupMarkers,
        shouldRenderNativeMap,
    ])

    useEffect(() => {
        if (!shouldShowDoorDeliveryMarker && hasMovedDoorDeliveryMapOnce) {
            setHasMovedDoorDeliveryMapOnce(false)
        }
    }, [hasMovedDoorDeliveryMapOnce, shouldShowDoorDeliveryMarker])

    useEffect(() => {
        if (!shouldShowDoorDeliveryMarker) {
            clearPendingDoorResolution()
        }
    }, [clearPendingDoorResolution, shouldShowDoorDeliveryMarker])

    useEffect(() => {
        return () => {
            clearPendingDoorResolution()
        }
    }, [clearPendingDoorResolution])

    const handleSelectDeliveryCountry = useCallback((countryCode: (typeof COUNTRY_SELECTOR_CODES)[number]) => {
        if (selectedDeliveryCountry === countryCode) {
            return
        }

        Keyboard.dismiss()
        clearPendingDoorResolution()
        setSelectedDeliveryCountry(countryCode)
        setSelectedDeliveryAddress(null)
        setSelectedDeliveryPoint(null)
        setDoorDeliveryDraft(null)
        setPickupPointDraft(null)
        setIsDoorFooterExpanded(false)
        setIsPickupFooterExpanded(false)
        setSelectionError(null)
        setPickupPointError(null)
        setSearch("")
        setSearchEnabled(true)
        setIsSearchFocused(false)
        setSearchFocusPoint(null)
        clearResults()
        lastFollowedUserPointRef.current = null
        moveToRegion(
            getDeliveryCountryViewport(countryCode).region,
            DELIVERY_CAMERA_DURATIONS.country,
        )
    }, [
        clearPendingDoorResolution,
        clearResults,
        moveToRegion,
        selectedDeliveryCountry,
    ])

    const getDoorDeliveryCameraRegion = useCallback(
        (point: Point) => {
            const currentCameraPosition = cameraPositionRef.current

            return {
                lat: point.lat,
                lon: point.lon,
                zoom: currentCameraPosition?.zoom ?? initialMapRegion.zoom,
                azimuth: currentCameraPosition?.azimuth ?? initialMapRegion.azimuth,
                tilt: currentCameraPosition?.tilt ?? initialMapRegion.tilt,
            }
        },
        [initialMapRegion.azimuth, initialMapRegion.tilt, initialMapRegion.zoom],
    )

    useEffect(() => {
        Animated.parallel([
            Animated.timing(doorChromeOpacity, {
                duration: shouldHideDoorDeliveryChrome ? 140 : 220,
                easing: shouldHideDoorDeliveryChrome ? Easing.out(Easing.quad) : Easing.out(Easing.cubic),
                toValue: shouldHideDoorDeliveryChrome ? 0 : 1,
                useNativeDriver: true,
            }),
            Animated.timing(doorTopControlsTranslateY, {
                duration: shouldHideDoorDeliveryChrome ? 140 : 220,
                easing: shouldHideDoorDeliveryChrome ? Easing.out(Easing.quad) : Easing.out(Easing.cubic),
                toValue: shouldHideDoorDeliveryChrome ? -18 : 0,
                useNativeDriver: true,
            }),
            Animated.timing(doorBottomControlsTranslateY, {
                duration: shouldHideDoorDeliveryChrome ? 140 : 220,
                easing: shouldHideDoorDeliveryChrome ? Easing.out(Easing.quad) : Easing.out(Easing.cubic),
                toValue: shouldHideDoorDeliveryChrome ? 120 : 0,
                useNativeDriver: true,
            }),
        ]).start()
    }, [
        doorBottomControlsTranslateY,
        doorChromeOpacity,
        doorTopControlsTranslateY,
        shouldHideDoorDeliveryChrome,
    ])

    useEffect(() => {
        if (!shouldFollowUser) {
            lastFollowedUserPointRef.current = null
            return
        }

        const lastPoint = lastFollowedUserPointRef.current
        if (lastPoint?.lat === userPoint.lat && lastPoint.lon === userPoint.lon) {
            return
        }

        lastFollowedUserPointRef.current = userPoint
        moveToRegion(
            getDeliveryRegion(userPoint),
            lastPoint ? DELIVERY_CAMERA_DURATIONS.follow : DELIVERY_CAMERA_DURATIONS.startup,
        )
    }, [moveToRegion, shouldFollowUser, userPoint])

    const focusUserLocation = useCallback(
        (nextPoint: Point, duration: number) => {
            Keyboard.dismiss()
            lastFollowedUserPointRef.current = nextPoint
            setSearchFocusPoint(null)
            setIsSearchFocused(false)
            setSearch("")
            setSearchEnabled(true)
            clearResults()
            moveToRegion(getDeliveryRegion(nextPoint), duration)
        },
        [clearResults, moveToRegion],
    )

    const handleGoBack = () => {
        if (router.canGoBack()) {
            router.back()
            return
        }

        router.push(ROUTES.discover)
    }

    const handleDismissSearchFocus = () => {
        Keyboard.dismiss()
        setIsSearchFocused(false)
        setSearchEnabled(false)
        clearResults()
    }

    const handleClosePickupFooterExtension = useCallback(() => {
        setIsPickupFooterExpanded(false)
    }, [])

    const handleCloseDoorFooterExtension = useCallback(() => {
        if (isResolvingDoorAddress) {
            return
        }

        setIsDoorFooterExpanded(false)
        setSelectionError(null)
    }, [isResolvingDoorAddress])

    const handleChangeSearch = (value: string) => {
        setSearch(value)
        setSearchEnabled(true)
        setSelectionError(null)
        setPickupPointError(null)
    }

    const handleSearchFocusChange = useCallback(
        (isFocused: boolean) => {
            setIsSearchFocused(isFocused)

            if (!isFocused) {
                return
            }

            setSearchEnabled(true)
            setSelectionError(null)
            setPickupPointError(null)
            void runSearch()
        },
        [runSearch],
    )

    const handleSubmitSearch = useCallback(() => {
        setSearchEnabled(true)
        setSelectionError(null)
        setPickupPointError(null)
        void runSearch()
    }, [runSearch])

    const applyDoorDeliveryGeocodeResult = useCallback(
        (
            geocodeResult: DeliveryGeoCodeResult,
            duration: number,
            options: {
                recenterMap?: boolean
                showCountryError?: boolean
            } = {},
        ) => {
            const { recenterMap = true, showCountryError = true } = options
            const nextCountryCode = getSupportedDeliveryCountryCode(geocodeResult.country_code)

            if (!supportsDoorDeliveryForCountry(nextCountryCode)) {
                if (showCountryError) {
                    Alert.alert(
                        translate("delivery.doorDeliveryOnlyRuTitle"),
                        translate("delivery.doorDeliveryOnlyRuMessage"),
                    )
                }

                return false
            }

            if (nextCountryCode !== activeCountryCode) {
                if (showCountryError) {
                    Alert.alert(
                        translate("delivery.countryMismatchTitle"),
                        translate("delivery.countryMismatchMessage"),
                    )
                }

                return false
            }

            const nextDraft = buildDoorDeliveryDraft(
                geocodeResult,
                nextCountryCode,
            )
            const nextPoint = {
                lat: nextDraft.latitude,
                lon: nextDraft.longitude,
            }

            const applyDoorDeliveryDraft = async () => {
                let deliveryCalculationErrorMessage: string | null = null

                try {
                    nextDraft.deliveryCalculation = await calculateDoorDelivery(nextDraft)
                } catch (deliveryCalculationError) {
                    showBackendErrorAlert(deliveryCalculationError)
                    deliveryCalculationErrorMessage = getDeliveryCalculationErrorMessage(deliveryCalculationError)
                }

                lastFollowedUserPointRef.current = null
                setIsDoorFooterExpanded(true)
                setDoorDeliveryDraft(nextDraft)
                setPickupPointDraft(null)
                setPickupPointError(null)
                setSelectionError(deliveryCalculationErrorMessage)
                setSearchFocusPoint(nextPoint)
                setSearch(nextDraft.address)
                setSearchEnabled(false)
                setIsSearchFocused(false)
                clearResults()
                if (recenterMap) {
                    moveToRegion(getDoorDeliveryCameraRegion(nextPoint), duration)
                }
                return true
            }

            return applyDoorDeliveryDraft()
        },
        [activeCountryCode, clearResults, getDoorDeliveryCameraRegion, moveToRegion],
    )

    const resolveDoorDeliveryPoint = useCallback(
        async (
            nextPoint: Point,
            duration: number,
            options: {
                recenterMap?: boolean
                silent?: boolean
            } = {},
        ) => {
            const { recenterMap = true, silent = false } = options

            if (arePointsClose(doorDeliveryPoint, nextPoint)) {
                return true
            }

            try {
                setIsDoorFooterExpanded(true)
                setSelectionError(null)
                setIsResolvingDoorAddress(true)
                const geocodeResult = await reverseGeocodeDeliveryPoint(nextPoint)
                return await applyDoorDeliveryGeocodeResult(geocodeResult, duration, {
                    recenterMap,
                    showCountryError: !silent,
                })
            } catch (resolveError) {
                showBackendErrorAlert(resolveError)
                if (!silent) {
                    Alert.alert(
                        translate("delivery.doorDeliveryResolveTitle"),
                        translate("delivery.doorDeliveryResolveMessage"),
                    )
                }

                return false
            } finally {
                setIsResolvingDoorAddress(false)
            }
        },
        [applyDoorDeliveryGeocodeResult, doorDeliveryPoint],
    )

    const handleLocateUser = async () => {
        logDeliveryFlow("locate user pressed", {
            hasUserLocation,
        })

        if (hasUserLocation) {
            logDeliveryFlow("locate user using cached location")
            focusUserLocation(userPoint, DELIVERY_CAMERA_DURATIONS.follow)
            return
        }

        const nextPoint = await requestUserLocation()
        logDeliveryFlow("locate user request completed", {
            resolved: Boolean(nextPoint),
        })
        if (!nextPoint) {
            Alert.alert(
                translate("delivery.locationUnavailableTitle"),
                translate("delivery.locationUnavailableMessage"),
            )
            return
        }

        focusUserLocation(nextPoint, DELIVERY_CAMERA_DURATIONS.startup)
    }

    useEffect(() => {
        if (!doorDeliveryPoint) {
            return
        }

        lastFollowedUserPointRef.current = null
        setSearchFocusPoint(doorDeliveryPoint)
        setSearch(doorDeliveryDraft?.address ?? "")
        setSearchEnabled(false)
        if (
            !cameraPositionRef.current
            || !arePointsClose(cameraPositionRef.current.point, doorDeliveryPoint)
        ) {
            moveToRegion(
                getDoorDeliveryCameraRegion(doorDeliveryPoint),
                DELIVERY_CAMERA_DURATIONS.search,
            )
        }
    }, [doorDeliveryDraft?.address, doorDeliveryPoint, getDoorDeliveryCameraRegion, moveToRegion])

    useEffect(() => {
        if (!pickupPoint || doorDeliveryPoint) {
            return
        }

        lastFollowedUserPointRef.current = null
        setSearchFocusPoint(pickupPoint)
        setIsSearchFocused(false)
        setSearch(getPickupPointAddress(pickupPointDraft))
        setSearchEnabled(false)
        clearResults()
        moveToRegion(getDeliveryRegion(pickupPoint, PICKUP_POINT_FOCUS_ZOOM), DELIVERY_CAMERA_DURATIONS.search)
    }, [clearResults, doorDeliveryPoint, moveToRegion, pickupPoint, pickupPointDraft])

    const handleChoosePickupPoint = useCallback(() => {
        if (!pickupPointDraft) {
            return
        }

        const choosePickupPoint = async () => {
            const nextPoint = {
                lat: pickupPointDraft.latitude,
                lon: pickupPointDraft.longitude,
            }

            try {
                setPickupPointError(null)

                const deliveryCalculation =
                    pickupPointDraft.provider === "cdek"
                        ? pickupPointDraft.deliveryCalculation
                          ?? await calculateCdekDelivery(
                              buildCdekPickupCalculationRequest(
                                  pickupPointDraft,
                                  activeCountryCode,
                              ),
                          )
                        : pickupPointDraft.provider === "yandex"
                          ? pickupPointDraft.deliveryCalculation
                            ?? await calculateYandexDelivery(pickupPointDraft.code)
                        : null

                if (!deliveryCalculation) {
                    throw new Error(translate("delivery.calculateError"))
                }

                const orderDraftPayload = buildPickupOrderDraftPayload(
                    pickupPointDraft,
                    deliveryCalculation,
                    activeCountryCode,
                )
                const nextDraft =
                    checkoutDraftId !== null
                        ? await updateOrderDraft(
                              checkoutDraftId,
                              buildOrderDraftAddressUpdatePayload(orderDraftPayload, shouldSyncBasketItems),
                          )
                        : null
                const nextBasket = checkoutDraftId === null
                    ? await updateBasketCheckout({
                          new_delivery_address: buildOrderDraftAddressUpdatePayload(orderDraftPayload, false).new_delivery_address,
                      })
                    : null

                if (nextDraft !== null) {
                    setOrderDraftSnapshot(nextDraft)
                }
                if (nextBasket !== null) {
                    setBasketSnapshot(nextBasket)
                }
                setSelectedDeliveryPoint(null)
                setSelectedDeliveryAddress(null)
                setIsDoorFooterExpanded(false)
                setDoorDeliveryDraft(null)
                setPickupPointDraft(null)

                lastFollowedUserPointRef.current = null
                setSearchFocusPoint(nextPoint)
                setIsSearchFocused(false)
                setSearch(getPickupPointAddress(pickupPointDraft) || pickupPointDraft.name)
                setSearchEnabled(false)
                clearResults()
                moveToRegion(
                    getDeliveryRegion(nextPoint, PICKUP_POINT_FOCUS_ZOOM),
                    DELIVERY_CAMERA_DURATIONS.search,
                )

                if (nextBasket !== null) {
                    router.replace(ROUTES.checkout)
                } else if (nextDraft !== null) {
                    router.replace(`${ROUTES.checkout}?draftId=${nextDraft.id}`)
                }
            } catch (deliveryCalculationError) {
                showBackendErrorAlert(deliveryCalculationError)
                setPickupPointError(getDeliveryCalculationErrorMessage(deliveryCalculationError))
            } finally {
                setIsResolvingPickupPoint(false)
            }
        }

        setIsResolvingPickupPoint(true)
        void choosePickupPoint()
    }, [activeCountryCode, checkoutDraftId, clearResults, moveToRegion, pickupPointDraft, router, shouldSyncBasketItems])

    const handleCopyPickupInfo = useCallback(async (value: string) => {
        if (!value) {
            return
        }

        await Clipboard.setStringAsync(value)
        Alert.alert(translate("profile.copiedTitle"), value)
    }, [])

    const handleChooseDoorDelivery = useCallback(() => {
        if (!doorDeliveryDraft) {
            return
        }

        const chooseDoorDelivery = async () => {
            try {
                setSelectionError(null)
                const nextDoorDeliveryDraft = {
                    ...doorDeliveryDraft,
                    provider: DOOR_DELIVERY_PROVIDER,
                }
                const deliveryCalculation =
                    doorDeliveryDraft.deliveryCalculation
                    ?? await calculateDoorDelivery(nextDoorDeliveryDraft)

                const orderDraftPayload = buildDoorOrderDraftPayload(
                    nextDoorDeliveryDraft,
                    deliveryCalculation,
                    activeCountryCode,
                )
                const nextDraft =
                    checkoutDraftId !== null
                        ? await updateOrderDraft(
                              checkoutDraftId,
                              buildOrderDraftAddressUpdatePayload(orderDraftPayload, shouldSyncBasketItems),
                          )
                        : null
                const nextBasket = checkoutDraftId === null
                    ? await updateBasketCheckout({
                          new_delivery_address: buildOrderDraftAddressUpdatePayload(orderDraftPayload, false).new_delivery_address,
                      })
                    : null

                if (nextDraft !== null) {
                    setOrderDraftSnapshot(nextDraft)
                }
                if (nextBasket !== null) {
                    setBasketSnapshot(nextBasket)
                }
                setPickupPointDraft(null)
                setPickupPointError(null)
                setSelectedDeliveryPoint(null)
                setSelectedDeliveryAddress(null)

                if (nextBasket !== null) {
                    router.replace(ROUTES.checkout)
                } else if (nextDraft !== null) {
                    router.replace(`${ROUTES.checkout}?draftId=${nextDraft.id}`)
                }
            } catch (deliveryCalculationError) {
                showBackendErrorAlert(deliveryCalculationError)
                setSelectionError(getDeliveryCalculationErrorMessage(deliveryCalculationError))
            } finally {
                setIsResolvingDoorAddress(false)
            }
        }

        setIsResolvingDoorAddress(true)
        void chooseDoorDelivery()
    }, [activeCountryCode, checkoutDraftId, doorDeliveryDraft, router, shouldSyncBasketItems])

    const handleOpenDeliveryPointOfficePage = useCallback(async (code: string) => {
        const officeUrl = `https://www.cdek.ru/ru/offices/view/${encodeURIComponent(code)}/`

        try {
            await Linking.openURL(officeUrl)
        } catch {
            Alert.alert(
                translate("delivery.pickupPointOfficePageErrorTitle"),
                translate("delivery.pickupPointOfficePageErrorMessage"),
            )
        }
    }, [])

    const handlePressDeliveryPoint = useCallback(async (provider: DeliveryPointProvider, code: string) => {
        if (pendingDeliveryPointCodeRef.current !== null) {
            return
        }

        if (shouldShowPickupFooterExtension) {
            return
        }

        pendingDeliveryPointCodeRef.current = code
        setIsPickupFooterExpanded(true)
        setIsResolvingPickupPoint(true)
        setPickupPointError(null)
        setIsDoorFooterExpanded(false)
        setDoorDeliveryDraft(null)
        setSelectionError(null)

        try {
            const deliveryPoint =
                provider === "yandex"
                    ? await getYandexDeliveryPoint(code)
                    : await getCdekDeliveryPoint(code)
            const nextDraft = buildPickupPointDraft({
                ...deliveryPoint,
                provider,
            })
            const nextPoint = {
                lat: nextDraft.latitude,
                lon: nextDraft.longitude,
            }

            if (provider === "cdek") {
                try {
                    nextDraft.deliveryCalculation = await calculateCdekDelivery(
                        buildCdekPickupCalculationRequest(
                            nextDraft,
                            activeCountryCode,
                        ),
                    )
                } catch (deliveryCalculationError) {
                    showBackendErrorAlert(deliveryCalculationError)
                    setPickupPointError(getDeliveryCalculationErrorMessage(deliveryCalculationError))
                }
            } else if (provider === "yandex") {
                try {
                    nextDraft.deliveryCalculation = await calculateYandexDelivery(nextDraft.code)
                } catch (deliveryCalculationError) {
                    showBackendErrorAlert(deliveryCalculationError)
                    setPickupPointError(getDeliveryCalculationErrorMessage(deliveryCalculationError))
                }
            }

            pendingDeliveryPointCodeRef.current = null
            lastFollowedUserPointRef.current = null
            setPickupPointDraft(nextDraft)
            setSearchFocusPoint(nextPoint)
            setIsSearchFocused(false)
            setSearch(getPickupPointAddress(nextDraft) || nextDraft.name)
            setSearchEnabled(false)
            clearResults()
            moveToRegion(getDeliveryRegion(nextPoint, PICKUP_POINT_FOCUS_ZOOM), DELIVERY_CAMERA_DURATIONS.search)
        } catch (deliveryPointError) {
            showBackendErrorAlert(deliveryPointError)
            pendingDeliveryPointCodeRef.current = null
            setPickupPointDraft(null)

            if (provider === "yandex" && deliveryPointError instanceof ApiError && deliveryPointError.status === 404) {
                setRemovedDeliveryPointKeys((currentKeys) => {
                    const nextKeys = new Set(currentKeys)
                    nextKeys.add(getDeliveryPointMarkerKey(provider, code))
                    return nextKeys
                })
            }

            setPickupPointError(
                deliveryPointError instanceof Error
                    ? deliveryPointError.message
                    : translate("delivery.pickupPointLoadError"),
            )
        } finally {
            setIsResolvingPickupPoint(false)
        }
    }, [activeCountryCode, clearResults, moveToRegion, shouldShowPickupFooterExtension])

    const handlePressResult = async (item: DeliveryGeoSuggestResult) => {
        Keyboard.dismiss()

        try {
            const geocodeResult = await geocodeDeliveryAddress(item.full_address, {
                uri: item.uri,
            })
            const nextPoint = {
                lat: geocodeResult.lat,
                lon: geocodeResult.lon,
            }

            const nextCountryCode = getSupportedDeliveryCountryCode(geocodeResult.country_code)
            if (nextCountryCode && nextCountryCode !== activeCountryCode) {
                Alert.alert(
                    translate("delivery.countryMismatchTitle"),
                    translate("delivery.countryMismatchMessage"),
                )
                return
            }

            if (supportsDoorDelivery) {
                await applyDoorDeliveryGeocodeResult(
                    geocodeResult,
                    DELIVERY_CAMERA_DURATIONS.search,
                    {
                        showCountryError: false,
                    },
                )
                return
            }

            setPickupPointDraft(null)
            setPickupPointError(null)
            setSearch(geocodeResult.address || item.full_address)
            setSearchEnabled(false)
            setIsSearchFocused(false)
            clearResults()
            setSearchFocusPoint(nextPoint)

            moveToRegion(
                getDeliverySelectionRegion(geocodeResult),
                DELIVERY_CAMERA_DURATIONS.search,
            )
        } catch (selectionError) {
            showBackendErrorAlert(selectionError)
            const message =
                selectionError instanceof Error
                    ? selectionError.message
                    : translate("delivery.searchAddressResolveMessage")

            Alert.alert(translate("delivery.searchAddressNotFoundTitle"), message)
        }
    }

    return (
        <MapFlowTemplate
            chromeOverlay={
                <View
                    pointerEvents="box-none"
                    style={deliveryScreenStyles.floatingControlsSafeArea}
                >
                    <Animated.View
                        pointerEvents={shouldHideDoorDeliveryChrome ? "none" : "box-none"}
                        style={[
                            deliveryScreenStyles.topMapControlsDock,
                            { top: insets.top + spacing.xs },
                            {
                                opacity: doorChromeOpacity,
                                transform: [{ translateY: doorTopControlsTranslateY }],
                            },
                        ]}
                    >
                        <DeliveryCornerButton
                            accessibilityLabel={translate("nav.back")}
                            iconPath={BACK_ARROW_PATH}
                            onPress={handleGoBack}
                        />

                        <View style={deliveryScreenStyles.topMapCountrySelectorWrap}>
                            <ScrollView
                                bounces={false}
                                contentContainerStyle={deliveryScreenStyles.topMapCountrySelectorContent}
                                horizontal
                                keyboardShouldPersistTaps="handled"
                                showsHorizontalScrollIndicator={false}
                                style={deliveryScreenStyles.topMapCountrySelectorScroll}
                            >
                                {COUNTRY_SELECTOR_CODES.map((countryCode) => {
                                    const isActive = activeCountryCode === countryCode

                                    return (
                                        <Pressable
                                            key={countryCode}
                                            accessibilityLabel={countryCode}
                                            accessibilityRole="button"
                                            onPress={() => {
                                                handleSelectDeliveryCountry(countryCode)
                                            }}
                                            style={({ pressed }) => [
                                                deliveryScreenStyles.countrySelectorButton,
                                                !isActive && deliveryScreenStyles.countrySelectorButtonInactive,
                                                pressed && deliveryScreenStyles.countrySelectorButtonPressed,
                                            ]}
                                        >
                                            <CountryFlag
                                                code={countryCode}
                                                style={deliveryScreenStyles.countrySelectorFlag}
                                            />
                                        </Pressable>
                                    )
                                })}
                            </ScrollView>
                        </View>

                        <DeliveryCornerButton
                            accessibilityLabel={translate("nav.myLocation")}
                            iconPath={MY_LOCATION_ICON_PATH}
                            isActive={shouldFollowUser}
                            onPress={() => {
                                void handleLocateUser()
                            }}
                        />
                    </Animated.View>

                    <KeyboardAvoidingView
                        behavior={Platform.OS === "ios" ? "padding" : "height"}
                        pointerEvents="box-none"
                        style={deliveryScreenStyles.floatingControlsFrame}
                    >
                        <View style={deliveryScreenStyles.floatingControlsStack} />

                        <Animated.View
                            pointerEvents={shouldHideDoorDeliveryChrome ? "none" : "box-none"}
                            style={{
                                opacity: doorChromeOpacity,
                                transform: [{ translateY: doorBottomControlsTranslateY }],
                            }}
                        >
                            <StickyFooterSurface
                                contentStyle={deliveryScreenStyles.bottomSearchPanelContent}
                                style={[
                                    deliveryScreenStyles.bottomSearchPanelDock,
                                    deliveryScreenStyles.bottomSearchPanelSurface,
                                ]}
                                variant="search"
                            >
                                {shouldShowDoorFooterExtension ? (
                                    <PickupPointFooterExtension
                                        actionLabel={getDeliveryActionLabel(
                                            doorDeliveryDraft?.deliveryCalculation,
                                            translate("delivery.doorDeliveryConfirm"),
                                        )}
                                        error={selectionError}
                                        inset
                                        isResolving={isResolvingDoorAddress}
                                        onChoose={handleChooseDoorDelivery}
                                        onClose={handleCloseDoorFooterExtension}
                                        onCopyInfo={handleCopyPickupInfo}
                                        rows={getDoorDeliveryInfoRows(doorDeliveryDraft)}
                                        title={
                                            doorDeliveryDraft?.address || translate("delivery.doorDeliveryTitle")
                                        }
                                    />
                                ) : null}
                                {!shouldShowDoorFooterExtension && shouldShowPickupFooterExtension ? (
                                    <PickupPointFooterExtension
                                        actionLabel={getPickupPointActionLabel(pickupPointDraft?.deliveryCalculation)}
                                        error={pickupPointError}
                                        inset
                                        isResolving={isResolvingPickupPoint}
                                        onChoose={handleChoosePickupPoint}
                                        onClose={handleClosePickupFooterExtension}
                                        onCopyInfo={handleCopyPickupInfo}
                                        onOpenOfficePage={
                                            pickupPointDraft?.provider === "cdek"
                                                ? () => {
                                                      void handleOpenDeliveryPointOfficePage(
                                                          pickupPointDraft.code,
                                                      )
                                                  }
                                                : null
                                        }
                                        rows={getPickupPointInfoRows(pickupPointDraft)}
                                        title={pickupPointDraft?.name || translate("delivery.pickupPointFallbackTitle")}
                                    />
                                ) : null}
                                <DeliverySearchPanel
                                    error={error ?? deliveryPointsError}
                                    isLoading={isLoading}
                                    onChangeText={handleChangeSearch}
                                    onFocusChange={handleSearchFocusChange}
                                    onSelectResult={handlePressResult}
                                    onSubmitSearch={handleSubmitSearch}
                                    results={results}
                                    value={search}
                                    variant="footer"
                                />
                            </StickyFooterSurface>
                        </Animated.View>
                    </KeyboardAvoidingView>
                </View>
            }
            overlay={null}
            style={deliveryScreenStyles.viewport}
        >
            <View collapsable={false} style={deliveryScreenStyles.mapBox}>
                {shouldRenderMap ? (
                    <ClusteredYamap
                        ref={mapRef}
                        clusterColor={CDEK_PICKUP_MARKER_OUTER_COLOR}
                        clusteredMarkers={mapMarkers}
                        initialRegion={initialMapRegion}
                        markerSize={42}
                        markerIcons={DELIVERY_CLUSTER_MARKER_ICONS}
                        onMapPress={
                            supportsDoorDelivery
                                ? ({ nativeEvent }) => {
                                      logDeliveryFlow("delivery map press received", {
                                          countryCode: activeCountryCode,
                                          lat: nativeEvent.lat,
                                          lon: nativeEvent.lon,
                                          visibleMarkerCount: mapMarkers.length,
                                      })
                                      clearPendingDoorResolution()
                                      setPickupPointDraft(null)
                                      setPickupPointError(null)
                                      void resolveDoorDeliveryPoint(
                                          nativeEvent,
                                          DELIVERY_CAMERA_DURATIONS.search,
                                      )
                                  }
                                : undefined
                        }
                        onMapLoaded={handleDeliveryMapLoaded}
                        onLayout={handleDeliveryMapLayout}
                        onCameraPositionChange={({ nativeEvent }) => {
                            cameraPositionRef.current = nativeEvent
                            clearPendingDoorResolution()

                            if (!isDoorDeliveryMapInteracting) {
                                logDeliveryFlow("delivery map camera movement started", {
                                    countryCode: activeCountryCode,
                                    lat: nativeEvent.point.lat,
                                    lon: nativeEvent.point.lon,
                                    reason: nativeEvent.reason,
                                    shouldShowDoorDeliveryMarker,
                                    visibleMarkerCount: mapMarkers.length,
                                    zoom: nativeEvent.zoom,
                                })
                                setIsDoorDeliveryMapInteracting(true)
                            }

                            if (shouldShowDoorDeliveryMarker && nativeEvent.reason === "GESTURES") {
                                if (!hasMovedDoorDeliveryMapOnce) {
                                    setHasMovedDoorDeliveryMapOnce(true)
                                }
                            }
                        }}
                        onCameraPositionChangeEnd={({ nativeEvent }) => {
                            cameraPositionRef.current = nativeEvent
                            logDeliveryFlow("delivery map camera movement ended", {
                                countryCode: activeCountryCode,
                                isResolvingDoorAddress,
                                lat: nativeEvent.point.lat,
                                lon: nativeEvent.point.lon,
                                reason: nativeEvent.reason,
                                shouldShowDoorDeliveryMarker,
                                visibleMarkerCount: mapMarkers.length,
                                zoom: nativeEvent.zoom,
                            })
                            setIsDoorDeliveryMapInteracting(false)

                            if (
                                shouldShowDoorDeliveryMarker
                                && !isResolvingDoorAddress
                                && nativeEvent.reason === "GESTURES"
                                && !arePointsClose(doorDeliveryPoint, nativeEvent.point)
                            ) {
                                pendingDoorResolutionTimeoutRef.current = setTimeout(() => {
                                    pendingDoorResolutionTimeoutRef.current = null

                                    if (!arePointsClose(cameraPositionRef.current?.point ?? null, nativeEvent.point)) {
                                        return
                                    }

                                    void resolveDoorDeliveryPoint(
                                        nativeEvent.point,
                                        DELIVERY_CAMERA_DURATIONS.follow,
                                        {
                                            recenterMap: false,
                                            silent: true,
                                        },
                                    )
                                }, DOOR_DELIVERY_LOOKUP_DELAY_MS)
                            }
                        }}
                        onMarkerPress={({ nativeEvent }) => {
                            logDeliveryFlow("delivery marker press received", {
                                countryCode: activeCountryCode,
                                iconKey: nativeEvent.iconKey,
                                hasData: Boolean(nativeEvent.data),
                                lat: nativeEvent.point.lat,
                                lon: nativeEvent.point.lon,
                            })
                            const markerPayload = getClusteredMarkerPayload(nativeEvent.data)
                            if (!markerPayload) {
                                logDeliveryFlow("delivery marker press ignored", {
                                    countryCode: activeCountryCode,
                                    reason: "missing marker payload",
                                })
                                return
                            }

                            void handlePressDeliveryPoint(
                                markerPayload.provider,
                                markerPayload.code,
                            )
                        }}
                        showUserPosition={hasUserLocation}
                        style={StyleSheet.absoluteFillObject}
                    />
                ) : mapKitStatus === "error" ? (
                    <View style={deliveryScreenStyles.mapFallback}>
                        <Text style={deliveryScreenStyles.mapFallbackText}>
                            {translate("delivery.mapUnavailable")}
                        </Text>
                    </View>
                ) : null}
                <EdgeBlur
                    height={Math.round(topMapEdgeBlurHeight)}
                    intensity={12}
                    opacity={0.14}
                    position="top"
                />
                <EdgeBlur
                    height={Math.round(bottomMapEdgeBlurHeight)}
                    intensity={12}
                    opacity={0.16}
                    position="bottom"
                />

                {shouldBlockPickupMarkers ? (
                    <View style={deliveryScreenStyles.pickupMarkersLoadingOverlay}>
                        <BlurView
                            intensity={34}
                            pointerEvents="none"
                            style={deliveryScreenStyles.pickupMarkersBlur}
                            tint="light"
                            {...(Platform.OS === "android"
                                ? { experimentalBlurMethod: "dimezisBlurView" as const }
                                : {})}
                        />
                        <View style={[
                            deliveryScreenStyles.loadingCard,
                            deliveryScreenStyles.pickupMarkersLoadingCard,
                        ]}>
                            <ActivityIndicator color={colors.primary} size="large" />
                            <Text style={deliveryScreenStyles.loadingText}>
                                {translate("delivery.loadingPickupPoints")}
                            </Text>
                        </View>
                    </View>
                ) : null}

                {shouldShowDoorDeliveryMarker ? (
                    <View
                        pointerEvents="none"
                        style={deliveryScreenStyles.doorDeliveryMarkerOverlay}
                    >
                        <DeliveryPlaceMarker
                            isFloating={isDoorDeliveryMapInteracting}
                            label={
                                hasMovedDoorDeliveryMapOnce
                                    ? undefined
                                    : translate("delivery.doorDeliveryMoveMapHint")
                            }
                        />
                    </View>
                ) : null}

                {isSearchActive ? (
                    <Pressable
                        accessibilityLabel={translate("nav.closeSearch")}
                        accessibilityRole="button"
                        onPress={handleDismissSearchFocus}
                        style={deliveryScreenStyles.searchOverlayDismiss}
                    >
                        <BlurView
                            intensity={45}
                            style={deliveryScreenStyles.searchMapBlur}
                            tint="light"
                            {...(Platform.OS === "android"
                                ? { experimentalBlurMethod: "dimezisBlurView" as const }
                                : {})}
                        />
                    </Pressable>
                ) : null}
            </View>
        </MapFlowTemplate>
    )
}
