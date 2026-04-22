import { BlurView } from "expo-blur"
import * as Clipboard from "expo-clipboard"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
    ActivityIndicator,
    Alert,
    Animated,
    Easing,
    Keyboard,
    KeyboardAvoidingView,
    Linking,
    Platform,
    Pressable,
    StyleSheet,
    Text,
    View,
} from "react-native"
import { useLocalSearchParams, useRouter } from "expo-router"
import { useSafeAreaInsets } from "react-native-safe-area-context"
import {
    ClusteredYamap,
    type CameraPosition,
    type Point,
} from "react-native-yamap"

import { DeliveryCornerButton } from "@/components/delivery/delivery-corner-button"
import { PickupPointFooterExtension } from "@/components/delivery/pickup-point-footer-extension"
import { DeliverySearchPanel } from "@/components/delivery/delivery-search-panel"
import { StickyFooterSurface } from "@/components/footer/sticky-footer"
import { BACK_ARROW_PATH, MY_LOCATION_ICON_PATH } from "@/components/header/app-header.constants"
import { CDEK_PICKUP_MARKER_OUTER_COLOR } from "@/components/maps/cdek-pickup-marker.constants"
import { DeliveryPlaceMarker } from "@/components/maps/delivery-place-marker"
import { MapFlowTemplate } from "@/components/templates/map-flow-template"
import { ROUTES } from "@/constants/routes"
import { clearBasketSnapshot } from "@/hooks/basket/basket-store"
import {
    setSelectedDeliveryAddress,
    useSelectedDeliveryAddress,
} from "@/hooks/delivery/delivery-address-selection-store"
import { useSelectedDeliveryCountry } from "@/hooks/delivery/delivery-country-selection-store"
import {
    setSelectedDeliveryPoint,
    useSelectedDeliveryPoint,
} from "@/hooks/delivery/delivery-point-selection-store"
import { setOrderDraftSnapshot } from "@/hooks/order-draft/order-draft-store"
import { useDeliveryGeoSearch } from "@/hooks/delivery/use-delivery-geo-search"
import { useDeliveryPointMarkers } from "@/hooks/delivery/use-delivery-point-markers"
import { translate } from "@/i18n/translations"
import {
    calculateCdekDelivery,
    calculateYandexDelivery,
    DEFAULT_DELIVERY_COUNTRY_CODE,
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
import { createOrderDraft, updateOrderDraft } from "@/services/api/order-drafts"
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
import type {
    DeliveryDoorDraft,
    DeliveryMapMarker,
    DeliveryPickupDraft,
} from "@/screens/delivery/delivery-screen.types"
import {
    arePointsClose,
    areCameraPositionsEquivalent,
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
    getDoorDeliveryPoint,
    getNearestPickupMarkers,
    getPickupPoint,
    getPickupPointAddress,
    getPickupPointInfoRows,
    parseBooleanSearchParam,
    parseDraftId,
} from "@/screens/delivery/delivery-screen.utils"
import { colors } from "@/theme/colors"
import { spacing } from "@/theme/spacing"

export default function DeliveryScreen() {
    const router = useRouter()
    const params = useLocalSearchParams<{ draftId?: string | string[]; syncBasket?: string | string[] }>()
    const checkoutDraftId = parseDraftId(params.draftId)
    const shouldSyncBasketItems = parseBooleanSearchParam(params.syncBasket)
    const insets = useSafeAreaInsets()
    const mapRef = useRef<ClusteredYamap | null>(null)
    const pendingDeliveryPointCodeRef = useRef<string | null>(null)
    const pendingDoorResolutionTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const lastFollowedUserPointRef = useRef<Point | null>(null)
    const cameraPositionRef = useRef<CameraPosition | null>(null)
    const [searchFocusPoint, setSearchFocusPoint] = useState<Point | null>(null)
    const [isSearchFocused, setIsSearchFocused] = useState(false)
    const [search, setSearch] = useState("")
    const [searchEnabled, setSearchEnabled] = useState(true)
    const [cameraPosition, setCameraPosition] = useState<CameraPosition | null>(null)
    const [hasMovedDoorDeliveryMapOnce, setHasMovedDoorDeliveryMapOnce] = useState(false)
    const [isDoorDeliveryMapInteracting, setIsDoorDeliveryMapInteracting] = useState(false)
    const selectedDeliveryAddress = useSelectedDeliveryAddress()
    const selectedDeliveryPoint = useSelectedDeliveryPoint()
    const selectedDeliveryCountry = useSelectedDeliveryCountry()
    const activeCountryCode = selectedDeliveryCountry ?? DEFAULT_DELIVERY_COUNTRY_CODE
    const [doorDeliveryDraft, setDoorDeliveryDraft] = useState<DeliveryDoorDraft | null>(
        selectedDeliveryAddress
            ? {
                  ...selectedDeliveryAddress,
                  provider: DOOR_DELIVERY_PROVIDER,
              }
            : null,
    )
    const [isDoorFooterExpanded, setIsDoorFooterExpanded] = useState(Boolean(selectedDeliveryAddress))
    const [pickupPointDraft, setPickupPointDraft] = useState<DeliveryPickupDraft | null>(
        selectedDeliveryPoint ? buildPickupPointDraft(selectedDeliveryPoint) : null,
    )
    const [isPickupFooterExpanded, setIsPickupFooterExpanded] = useState(Boolean(selectedDeliveryPoint))
    const [isResolvingDoorAddress, setIsResolvingDoorAddress] = useState(false)
    const [isResolvingPickupPoint, setIsResolvingPickupPoint] = useState(false)
    const [removedDeliveryPointKeys, setRemovedDeliveryPointKeys] = useState<Set<string>>(() => new Set())
    const [selectionError, setSelectionError] = useState<string | null>(null)
    const [pickupPointError, setPickupPointError] = useState<string | null>(null)
    const {
        hasUserLocation,
        requestUserLocation,
        userPoint,
    } = useDeliveryLocation()
    const { handleMapLoaded, moveToRegion } = useDeliveryMapCamera(mapRef)
    const supportsDoorDelivery = supportsDoorDeliveryForCountry(activeCountryCode)
    const {
        deliveryPointMarkers,
        error: deliveryPointsError,
        isLoading: isDeliveryPointsLoading,
    } = useDeliveryPointMarkers(activeCountryCode)
    const doorDeliveryPoint = useMemo(
        () => getDoorDeliveryPoint(doorDeliveryDraft),
        [doorDeliveryDraft],
    )
    const pickupPoint = useMemo(
        () => getPickupPoint(pickupPointDraft),
        [pickupPointDraft],
    )
    const searchOriginPoint = searchFocusPoint ?? doorDeliveryPoint ?? pickupPoint ?? userPoint
    const { clearResults, error, isLoading, results, runSearch } = useDeliveryGeoSearch(
        search,
        searchOriginPoint,
        searchEnabled,
    )
    const isSearchActive = isSearchFocused
    const hasVisibleSearchFeedback = isLoading || Boolean(error) || results.length > 0
    const isMapLoading = isDeliveryPointsLoading && deliveryPointMarkers.length === 0
    const shouldRenderMap = true
    const shouldFollowUser =
        hasUserLocation
        && selectedDeliveryCountry === null
        && searchFocusPoint === null
        && doorDeliveryPoint === null
        && pickupPoint === null
    const shouldShowPickupFooterExtension =
        isPickupFooterExpanded &&
        !hasVisibleSearchFeedback &&
        Boolean(isResolvingPickupPoint || pickupPointDraft || pickupPointError)
    const shouldShowDoorFooterExtension =
        supportsDoorDelivery &&
        isDoorFooterExpanded &&
        !hasVisibleSearchFeedback &&
        Boolean(isResolvingDoorAddress || doorDeliveryDraft || selectionError)
    const shouldShowDoorDeliveryMarker =
        supportsDoorDelivery
        && !hasVisibleSearchFeedback
        && !shouldShowPickupFooterExtension
        && isDoorFooterExpanded
        && Boolean(isResolvingDoorAddress || doorDeliveryDraft)
    const shouldHideDoorDeliveryChrome = isDoorDeliveryMapInteracting
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
    const markerFocusPoint =
        cameraPosition?.point ?? searchFocusPoint ?? pickupPoint ?? doorDeliveryPoint ?? initialMapRegion
    const mapMarkers = useMemo(
        () => getNearestPickupMarkers(pickupMarkers, markerFocusPoint, MAX_NATIVE_PICKUP_MARKERS),
        [markerFocusPoint, pickupMarkers],
    )

    const clearPendingDoorResolution = useCallback(() => {
        if (!pendingDoorResolutionTimeoutRef.current) {
            return
        }

        clearTimeout(pendingDoorResolutionTimeoutRef.current)
        pendingDoorResolutionTimeoutRef.current = null
    }, [])

    useEffect(() => {
        setRemovedDeliveryPointKeys(new Set())
    }, [activeCountryCode])

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

        router.push(ROUTES.home)
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
            } catch {
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
        if (hasUserLocation) {
            focusUserLocation(userPoint, DELIVERY_CAMERA_DURATIONS.follow)
            return
        }

        const nextPoint = await requestUserLocation()
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
                        : await createOrderDraft(orderDraftPayload)

                setOrderDraftSnapshot(nextDraft)
                if (checkoutDraftId === null) {
                    clearBasketSnapshot()
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

                router.replace(`${ROUTES.checkout}?draftId=${nextDraft.id}`)
            } catch (deliveryCalculationError) {
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
                        : await createOrderDraft(orderDraftPayload)

                setOrderDraftSnapshot(nextDraft)
                if (checkoutDraftId === null) {
                    clearBasketSnapshot()
                }
                setPickupPointDraft(null)
                setPickupPointError(null)
                setSelectedDeliveryPoint(null)
                setSelectedDeliveryAddress(null)

                router.replace(`${ROUTES.checkout}?draftId=${nextDraft.id}`)
            } catch (deliveryCalculationError) {
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
                    setPickupPointError(getDeliveryCalculationErrorMessage(deliveryCalculationError))
                }
            } else if (provider === "yandex") {
                try {
                    nextDraft.deliveryCalculation = await calculateYandexDelivery(nextDraft.code)
                } catch (deliveryCalculationError) {
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
            const message =
                selectionError instanceof Error
                    ? selectionError.message
                    : "Не удалось определить координаты выбранного адреса."

            Alert.alert("Не удалось найти адрес", message)
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
            overlay={
                isMapLoading ? (
                    <View style={deliveryScreenStyles.loadingOverlay}>
                        <View style={deliveryScreenStyles.loadingCard}>
                            <ActivityIndicator color={colors.primary} size="large" />
                            <Text style={deliveryScreenStyles.loadingText}>
                                {"Загружаем пункты выдачи"}
                            </Text>
                        </View>
                    </View>
                ) : null
            }
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
                        onMapLoaded={handleMapLoaded}
                        onCameraPositionChange={({ nativeEvent }) => {
                            cameraPositionRef.current = nativeEvent
                            clearPendingDoorResolution()

                            if (!isDoorDeliveryMapInteracting) {
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
                            setCameraPosition((currentCameraPosition) =>
                                areCameraPositionsEquivalent(currentCameraPosition, nativeEvent)
                                    ? currentCameraPosition
                                    : nativeEvent,
                            )
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
                            const markerPayload = getClusteredMarkerPayload(nativeEvent.data)
                            if (!markerPayload) {
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
