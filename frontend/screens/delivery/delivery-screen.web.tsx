import { BlurView } from "expo-blur"
import * as Clipboard from "expo-clipboard"
import { useCallback, useEffect, useMemo, useState } from "react"
import { Alert, Linking, Pressable, ScrollView, View, useWindowDimensions } from "react-native"
import { useLocalSearchParams, useRouter } from "expo-router"
import { SafeAreaView } from "react-native-safe-area-context"

import { DeliveryCornerButton } from "@/components/delivery/delivery-corner-button"
import { PickupPointFooterExtension } from "@/components/delivery/pickup-point-footer-extension"
import { DeliverySearchPanel } from "@/components/delivery/delivery-search-panel"
import { CountryFlag } from "@/components/country-flag/country-flag"
import { COUNTRY_SELECTOR_CODES } from "@/components/country-flag/country-flag.consts"
import { EdgeBlur } from "@/components/effects/edge-blur"
import { StickyFooterSurface } from "@/components/footer/sticky-footer"
import { BACK_ARROW_PATH, SEARCH_ICON_PATH } from "@/components/header/app-header.constants"
import {
    CDEK_PICKUP_MARKER_LABEL,
    YANDEX_PICKUP_MARKER_LABEL,
} from "@/components/maps/cdek-pickup-marker.constants"
import { YandexMapWeb } from "@/components/maps/yandex-map.web"
import type { YandexMapMarker } from "@/components/maps/yandex-map.web.types"
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
import { translate } from "@/i18n/translations"
import { useDeliveryPointMarkers } from "@/hooks/delivery/use-delivery-point-markers"
import {
    calculateCdekDelivery,
    calculateYandexDelivery,
    DEFAULT_DELIVERY_COUNTRY_CODE,
    getCdekDeliveryPoint,
    getYandexDeliveryPoint,
    geocodeDeliveryAddress,
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
import {
    DOOR_DELIVERY_PROVIDER,
    DEFAULT_DELIVERY_POINT,
    DEFAULT_DELIVERY_ZOOM,
    PICKUP_POINT_FOCUS_ZOOM,
    getDeliveryCountryViewport,
    getDeliverySelectionZoom,
    getSupportedDeliveryCountryCode,
    supportsDoorDeliveryForCountry,
} from "@/screens/delivery/delivery-screen.constants"
import {
    calculateDoorDelivery,
    getDeliveryActionLabel,
    getPickupPointActionLabel,
} from "@/screens/delivery/delivery-calculation"
import { deliveryScreenStyles } from "@/screens/delivery/delivery-screen.styles"
import { useDeliveryFlowController } from "@/screens/delivery/use-delivery-flow-controller"
import {
    arePointsClose,
    buildCdekPickupCalculationRequest,
    buildDoorDeliveryDraft,
    buildDoorOrderDraftPayload,
    buildOrderDraftAddressUpdatePayload,
    buildPickupOrderDraftPayload,
    buildPickupPointDraft,
    getDeliveryCalculationErrorMessage,
    getDeliveryPointMarkerKey,
    getDoorDeliveryInfoRows,
    getPickupPointAddress,
    getPickupPointInfoRows,
    parseBooleanSearchParam,
    parseDraftId,
} from "@/screens/delivery/delivery-screen.utils"
import { deliveryScreenWebStyles } from "@/screens/delivery/delivery-screen.web.styles"
import { showBackendErrorAlert } from "@/utils/errors"

export default function DeliveryScreen() {
    const router = useRouter()
    const params = useLocalSearchParams<{ draftId?: string | string[]; syncBasket?: string | string[] }>()
    const checkoutDraftId = parseDraftId(params.draftId)
    const shouldSyncBasketItems = parseBooleanSearchParam(params.syncBasket)
    const { width: windowWidth } = useWindowDimensions()
    const isDesktop = windowWidth >= 1100
    const isTablet = windowWidth >= 760
    const selectedDeliveryAddress = useSelectedDeliveryAddress()
    const selectedDeliveryPoint = useSelectedDeliveryPoint()
    const selectedDeliveryCountry = useSelectedDeliveryCountry()
    const [isSearchOpen, setIsSearchOpen] = useState(false)
    const [point, setPoint] = useState({
        lat: getDeliveryCountryViewport(selectedDeliveryCountry ?? DEFAULT_DELIVERY_COUNTRY_CODE).region.lat,
        lon: getDeliveryCountryViewport(selectedDeliveryCountry ?? DEFAULT_DELIVERY_COUNTRY_CODE).region.lon,
    })
    const [userPoint, setUserPoint] = useState(DEFAULT_DELIVERY_POINT)
    const [hasUserLocation, setHasUserLocation] = useState(false)
    const [mapZoom, setMapZoom] = useState(
        getDeliveryCountryViewport(selectedDeliveryCountry ?? DEFAULT_DELIVERY_COUNTRY_CODE).region.zoom ?? DEFAULT_DELIVERY_ZOOM,
    )
    const {
        activeCountryCode,
        clearResults,
        doorDeliveryDraft,
        doorDeliveryPoint,
        error,
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
        searchPanelExpanded: isSearchOpen,
    })
    const { deliveryPointMarkers } = useDeliveryPointMarkers(activeCountryCode)
    const shouldFollowUser =
        hasUserLocation
        && selectedDeliveryCountry === null
        && searchFocusPoint === null
        && doorDeliveryPoint === null
        && pickupPoint === null
    const mapMarkers = useMemo<YandexMapMarker[]>(
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
                code: deliveryPointMarker.code,
                label:
                    deliveryPointMarker.provider === "yandex"
                        ? YANDEX_PICKUP_MARKER_LABEL
                        : CDEK_PICKUP_MARKER_LABEL,
                lat: deliveryPointMarker.latitude,
                lon: deliveryPointMarker.longitude,
                provider: deliveryPointMarker.provider,
            })),
        [deliveryPointMarkers, removedDeliveryPointKeys],
    )

    useEffect(() => {
        setRemovedDeliveryPointKeys(new Set())
    }, [activeCountryCode])

    useEffect(() => {
        if (typeof window === "undefined" || !("geolocation" in navigator)) {
            return
        }

        let isMounted = true
        const geolocationOptions = {
            enableHighAccuracy: false,
            maximumAge: 60_000,
            timeout: 10_000,
        }

        const handlePosition = ({ coords }: GeolocationPosition) => {
            const nextPoint = {
                lat: coords.latitude,
                lon: coords.longitude,
            }

            if (!isMounted) {
                return
            }

            setUserPoint(nextPoint)
            setHasUserLocation(true)
        }

        const handlePositionError = (positionError: GeolocationPositionError) => {
            console.error("[delivery-web] Failed to get user location.", positionError)
        }

        navigator.geolocation.getCurrentPosition(
            handlePosition,
            handlePositionError,
            geolocationOptions,
        )

        const watchId = navigator.geolocation.watchPosition(
            handlePosition,
            handlePositionError,
            geolocationOptions,
        )

        return () => {
            isMounted = false
            navigator.geolocation.clearWatch(watchId)
        }
    }, [])

    useEffect(() => {
        if (!shouldFollowUser) {
            return
        }

        setPoint(userPoint)
    }, [shouldFollowUser, userPoint])

    const handleSelectDeliveryCountry = useCallback((countryCode: (typeof COUNTRY_SELECTOR_CODES)[number]) => {
        if (selectedDeliveryCountry === countryCode) {
            return
        }

        const nextRegion = getDeliveryCountryViewport(countryCode).region

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
        setIsSearchOpen(false)
        setIsSearchFocused(false)
        setSearchFocusPoint(null)
        clearResults()
        setPoint({
            lat: nextRegion.lat,
            lon: nextRegion.lon,
        })
        setMapZoom(nextRegion.zoom ?? DEFAULT_DELIVERY_ZOOM)
    }, [clearResults, selectedDeliveryCountry])

    const applyDoorDeliveryGeocodeResult = useCallback(
        async (geocodeResult: DeliveryGeoCodeResult) => {
            const nextCountryCode = getSupportedDeliveryCountryCode(geocodeResult.country_code)

            if (!supportsDoorDeliveryForCountry(nextCountryCode)) {
                setSelectionError(translate("delivery.doorDeliveryOnlyRuMessage"))
                return false
            }

            if (nextCountryCode !== activeCountryCode) {
                setSelectionError(translate("delivery.countryMismatchMessage"))
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

            let deliveryCalculationErrorMessage: string | null = null

            try {
                nextDraft.deliveryCalculation = await calculateDoorDelivery(nextDraft)
            } catch (deliveryCalculationError) {
                showBackendErrorAlert(deliveryCalculationError)
                deliveryCalculationErrorMessage = getDeliveryCalculationErrorMessage(deliveryCalculationError)
            }

            setIsDoorFooterExpanded(true)
            setDoorDeliveryDraft(nextDraft)
            setPickupPointDraft(null)
            setPickupPointError(null)
            setSearchFocusPoint(nextPoint)
            setSearch(nextDraft.address)
            setSearchEnabled(false)
            setIsSearchOpen(false)
            setIsSearchFocused(false)
            setSelectionError(deliveryCalculationErrorMessage)
            clearResults()
            setPoint(nextPoint)
            setMapZoom(PICKUP_POINT_FOCUS_ZOOM)
            return true
        },
        [activeCountryCode, clearResults],
    )

    const resolveDoorDeliveryPoint = useCallback(
        async (
            nextPoint: {
                lat: number
                lon: number
            },
            options: {
                silent?: boolean
            } = {},
        ) => {
            const { silent = false } = options

            if (arePointsClose(doorDeliveryPoint, nextPoint)) {
                return true
            }

            try {
                setIsDoorFooterExpanded(true)
                setIsResolvingDoorAddress(true)
                const geocodeResult = await reverseGeocodeDeliveryPoint(nextPoint)
                return await applyDoorDeliveryGeocodeResult(geocodeResult)
            } catch (resolveError) {
                showBackendErrorAlert(resolveError)
                if (!silent) {
                    setSelectionError(
                        resolveError instanceof Error
                            ? resolveError.message
                            : translate("delivery.doorDeliveryResolveMessage"),
                    )
                }

                return false
            } finally {
                setIsResolvingDoorAddress(false)
            }
        },
        [applyDoorDeliveryGeocodeResult, doorDeliveryPoint],
    )

    useEffect(() => {
        if (!doorDeliveryPoint) {
            return
        }

        setSearchFocusPoint(doorDeliveryPoint)
        setSearch(doorDeliveryDraft?.address ?? "")
        setSearchEnabled(false)
        setPoint(doorDeliveryPoint)
        setMapZoom(PICKUP_POINT_FOCUS_ZOOM)
    }, [doorDeliveryDraft?.address, doorDeliveryPoint])

    useEffect(() => {
        if (!pickupPoint || doorDeliveryPoint) {
            return
        }

        setSearchFocusPoint(pickupPoint)
        setIsSearchOpen(false)
        setIsSearchFocused(false)
        setSearch(getPickupPointAddress(pickupPointDraft))
        setSearchEnabled(false)
        clearResults()
        setPoint(pickupPoint)
        setMapZoom(16)
    }, [clearResults, doorDeliveryPoint, pickupPoint, pickupPointDraft])

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

    const handleOpenSearch = () => {
        setIsSearchOpen(true)
    }

    const handleCloseSearch = () => {
        setIsSearchOpen(false)
        setIsSearchFocused(false)
        setSearchEnabled(false)
        setSelectionError(null)
        setPickupPointError(null)
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

    const handleGoBack = () => {
        if (router.canGoBack()) {
            router.back()
            return
        }

        router.push(ROUTES.discover)
    }

    const handleMapClick = useCallback(
        (nextPoint: { lat: number; lon: number }) => {
            if (!supportsDoorDelivery) {
                return
            }

            setPickupPointDraft(null)
            setPickupPointError(null)
            setSelectionError(null)
            void resolveDoorDeliveryPoint(nextPoint)
        },
        [resolveDoorDeliveryPoint, supportsDoorDelivery],
    )

    const handlePressDeliveryPoint = useCallback(async (provider: DeliveryPointProvider, code: string) => {
        if (shouldShowPickupFooterExtension) {
            return
        }

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

            setPickupPointDraft(nextDraft)
            setSearch(getPickupPointAddress(nextDraft) || nextDraft.name)
            setSearchEnabled(false)
            setIsSearchOpen(false)
            setIsSearchFocused(false)
            clearResults()
            setSearchFocusPoint(nextPoint)
            setPoint(nextPoint)
            setMapZoom(PICKUP_POINT_FOCUS_ZOOM)
        } catch (deliveryPointError) {
            showBackendErrorAlert(deliveryPointError)
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
    }, [activeCountryCode, clearResults, shouldShowPickupFooterExtension])

    const handlePressResult = async (result: DeliveryGeoSuggestResult) => {
        try {
            const geocodeResult = await geocodeDeliveryAddress(result.full_address, {
                uri: result.uri,
            })
            const nextPoint = {
                lat: geocodeResult.lat,
                lon: geocodeResult.lon,
            }
            const nextCountryCode = getSupportedDeliveryCountryCode(geocodeResult.country_code)

            if (nextCountryCode && nextCountryCode !== activeCountryCode) {
                setIsDoorFooterExpanded(true)
                setSelectionError(translate("delivery.countryMismatchMessage"))
                return
            }

            if (supportsDoorDelivery) {
                await applyDoorDeliveryGeocodeResult(geocodeResult)
                return
            }

            setPickupPointDraft(null)
            setPickupPointError(null)
            setSearch(geocodeResult.address || result.full_address)
            setSearchEnabled(false)
            setIsSearchOpen(false)
            setIsSearchFocused(false)
            setSelectionError(null)
            clearResults()
            setSearchFocusPoint(nextPoint)
            setPoint(nextPoint)
            setMapZoom(getDeliverySelectionZoom(geocodeResult))
        } catch (lookupError) {
            showBackendErrorAlert(lookupError)
            setIsDoorFooterExpanded(true)
            setSelectionError(
                lookupError instanceof Error
                    ? lookupError.message
                    : "Не удалось определить координаты выбранного адреса.",
            )
        }
    }

    const handleChoosePickupPoint = useCallback(() => {
        if (!pickupPointDraft) {
            return
        }

        const choosePickupPoint = async () => {
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
    }, [activeCountryCode, checkoutDraftId, pickupPointDraft, router, shouldSyncBasketItems])

    const handleCopyPickupInfo = useCallback(async (value: string) => {
        if (!value) {
            return
        }

        await Clipboard.setStringAsync(value)
        Alert.alert(translate("profile.copiedTitle"), value)
    }, [])

    const handleOpenDeliveryPointOfficePage = useCallback(async (code: string) => {
        const officeUrl = `https://www.cdek.ru/ru/offices/view/${encodeURIComponent(code)}/`

        try {
            await Linking.openURL(officeUrl)
        } catch {
            setPickupPointError(translate("delivery.pickupPointOfficePageErrorMessage"))
        }
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

    return (
        <MapFlowTemplate
            chromeOverlay={
                <SafeAreaView
                    edges={["left", "right", "bottom"]}
                    pointerEvents="box-none"
                    style={deliveryScreenStyles.floatingControlsSafeArea}
                >
                    <View
                        pointerEvents="box-none"
                        style={[
                            deliveryScreenStyles.floatingControlsFrame,
                            deliveryScreenWebStyles.floatingControlsFrame,
                            isDesktop
                                ? deliveryScreenWebStyles.floatingControlsFrameDesktop
                                : isTablet
                                  ? deliveryScreenWebStyles.floatingControlsFrameTablet
                                  : null,
                        ]}
                    >
                        <View
                            style={[
                                deliveryScreenStyles.floatingControlsStack,
                                deliveryScreenWebStyles.floatingControlsStack,
                                isDesktop
                                    ? deliveryScreenWebStyles.floatingControlsStackDesktop
                                    : isTablet
                                      ? deliveryScreenWebStyles.floatingControlsStackTablet
                                      : null,
                            ]}
                        >
                            <ScrollView
                                bounces={false}
                                contentContainerStyle={deliveryScreenStyles.countrySelectorContent}
                                horizontal
                                keyboardShouldPersistTaps="handled"
                                showsHorizontalScrollIndicator={false}
                                style={deliveryScreenStyles.countrySelectorScroll}
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

                            <StickyFooterSurface
                                contentStyle={[
                                    deliveryScreenStyles.webMapFooterContent,
                                    isDesktop
                                        ? deliveryScreenWebStyles.footerContentDesktop
                                        : isTablet
                                          ? deliveryScreenWebStyles.footerContentTablet
                                          : null,
                                ]}
                                style={deliveryScreenWebStyles.footerSurface}
                                variant="search"
                            >
                                {shouldShowDoorFooterExtension ? (
                                    <PickupPointFooterExtension
                                        actionLabel={getDeliveryActionLabel(
                                            doorDeliveryDraft?.deliveryCalculation,
                                            translate("delivery.doorDeliveryConfirm"),
                                        )}
                                        error={selectionError}
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

                                <View
                                    style={[
                                        deliveryScreenStyles.floatingControlsRow,
                                        deliveryScreenWebStyles.floatingControlsRow,
                                    ]}
                                >
                                    <DeliveryCornerButton
                                        accessibilityLabel={translate("nav.back")}
                                        iconPath={BACK_ARROW_PATH}
                                        onPress={handleGoBack}
                                    />

                                    {isSearchOpen ? (
                                        <View
                                            style={[
                                                deliveryScreenStyles.searchPanelDock,
                                                deliveryScreenStyles.searchPanelDockFooter,
                                            ]}
                                        >
                                            <DeliverySearchPanel
                                                autoFocus
                                                error={
                                                    shouldShowDoorFooterExtension
                                                        ? null
                                                        : selectionError ?? error
                                                }
                                                isLoading={isLoading}
                                                onChangeText={handleChangeSearch}
                                                onClose={handleCloseSearch}
                                                onFocusChange={handleSearchFocusChange}
                                                onSelectResult={handlePressResult}
                                                onSubmitSearch={handleSubmitSearch}
                                                results={results}
                                                value={search}
                                            />
                                        </View>
                                    ) : (
                                        <View
                                            style={[
                                                deliveryScreenStyles.searchPanelDock,
                                                deliveryScreenStyles.searchPanelDockFooter,
                                            ]}
                                        >
                                            <View style={{ alignItems: "flex-end" }}>
                                                <DeliveryCornerButton
                                                    accessibilityLabel={translate("nav.search")}
                                                    iconPath={SEARCH_ICON_PATH}
                                                    onPress={handleOpenSearch}
                                                />
                                            </View>
                                        </View>
                                    )}
                                </View>
                            </StickyFooterSurface>
                        </View>
                    </View>
                </SafeAreaView>
            }
            style={deliveryScreenWebStyles.container}
        >
            <View style={deliveryScreenWebStyles.mapLayer}>
                <YandexMapWeb
                    center={point}
                    markers={mapMarkers}
                    markerLabel={translate("delivery.pickupPointFallbackTitle")}
                    onMapClick={handleMapClick}
                    onMarkerClick={(marker) => {
                        if (!marker.code) {
                            return
                        }

                        void handlePressDeliveryPoint(marker.provider ?? "cdek", marker.code)
                    }}
                    zoom={mapZoom}
                />
                <EdgeBlur
                    height={24}
                    intensity={10}
                    opacity={0.12}
                    position="top"
                />
                <EdgeBlur
                    height={28}
                    intensity={10}
                    opacity={0.14}
                    position="bottom"
                />
            </View>

            {isSearchActive ? (
                <Pressable
                    accessibilityLabel={translate("nav.closeSearch")}
                    accessibilityRole="button"
                    onPress={handleCloseSearch}
                    style={deliveryScreenWebStyles.searchDismissOverlay}
                >
                    <BlurView
                        intensity={45}
                        style={deliveryScreenWebStyles.searchBlur}
                        tint="light"
                    />
                </Pressable>
            ) : null}
        </MapFlowTemplate>
    )
}
