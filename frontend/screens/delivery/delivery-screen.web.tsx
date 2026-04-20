import { BlurView } from "expo-blur"
import * as Clipboard from "expo-clipboard"
import { useCallback, useEffect, useMemo, useState } from "react"
import { Alert, Linking, Pressable, View, useWindowDimensions } from "react-native"
import { useRouter } from "expo-router"
import { SafeAreaView } from "react-native-safe-area-context"

import { DeliveryCornerButton } from "@/components/delivery/delivery-corner-button"
import { PickupPointFooterExtension } from "@/components/delivery/pickup-point-footer-extension"
import { DeliverySearchPanel } from "@/components/delivery/delivery-search-panel"
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
import {
    setSelectedDeliveryAddress,
    useSelectedDeliveryAddress,
} from "@/hooks/delivery/delivery-address-selection-store"
import {
    useSelectedDeliveryCountry,
} from "@/hooks/delivery/delivery-country-selection-store"
import {
    setSelectedDeliveryPoint,
    useSelectedDeliveryPoint,
} from "@/hooks/delivery/delivery-point-selection-store"
import type { SelectedDeliveryPoint } from "@/hooks/delivery/delivery-point-selection-store.types"
import { useDeliveryGeoSearch } from "@/hooks/delivery/use-delivery-geo-search"
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
    CdekDeliveryCalculation,
    DeliveryCountryCode,
    DeliveryGeoCodeResult,
    DeliveryGeoSuggestResult,
    DeliveryPointDetails,
    DeliveryPointProvider,
} from "@/services/api/delivery.types"
import {
    DEFAULT_DELIVERY_POINT,
    DEFAULT_DELIVERY_ZOOM,
    PICKUP_POINT_FOCUS_ZOOM,
    getDeliverySelectionZoom,
    getSupportedDeliveryCountryCode,
    supportsDoorDeliveryForCountry,
} from "@/screens/delivery/delivery-screen.constants"
import {
    getDeliveryActionLabel,
    getPickupPointActionLabel,
} from "@/screens/delivery/delivery-calculation"
import {
    calculateDoorDelivery,
    getDoorDeliveryProviderOptions,
    normalizeDoorDeliveryProvider,
} from "@/screens/delivery/delivery-door-provider"
import { deliveryScreenStyles } from "@/screens/delivery/delivery-screen.styles"
import type { DeliveryDoorDraft } from "@/screens/delivery/delivery-screen.types"
import { deliveryScreenWebStyles } from "@/screens/delivery/delivery-screen.web.styles"

type DeliveryPickupDraft = SelectedDeliveryPoint & {
    nearest_metro_station?: string | null
    nearest_station?: string | null
    note?: string | null
    emails?: string[]
    phones?: string[]
}

type DeliveryInfoRow = {
    key: string
    label: string
    value: string
}

function buildDoorDeliveryDraft(
    geocodeResult: DeliveryGeoCodeResult,
    provider: DeliveryPointProvider,
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
        provider,
        subtitle: geocodeResult.subtitle,
    }
}

function buildPickupPointDraft(
    deliveryPoint:
        | (DeliveryPointDetails & { provider?: DeliveryPointProvider })
        | SelectedDeliveryPoint
        | DeliveryPickupDraft,
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

function buildSelectedDeliveryPoint(
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

function getDeliveryCalculationErrorMessage(deliveryCalculationError: unknown) {
    return deliveryCalculationError instanceof Error
        ? deliveryCalculationError.message
        : translate("delivery.calculateError")
}

function buildCdekPickupCalculationRequest(
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

function getDeliveryPointMarkerKey(provider: DeliveryPointProvider, code: string) {
    return `${provider}:${code}`
}

function getDoorDeliveryPoint(doorDeliveryDraft: DeliveryDoorDraft | null) {
    if (!doorDeliveryDraft) {
        return null
    }

    return {
        lat: doorDeliveryDraft.latitude,
        lon: doorDeliveryDraft.longitude,
    }
}

function getPickupPoint(pickupPointDraft: DeliveryPickupDraft | null) {
    if (!pickupPointDraft) {
        return null
    }

    return {
        lat: pickupPointDraft.latitude,
        lon: pickupPointDraft.longitude,
    }
}

function getPickupPointAddress(pickupPointDraft: DeliveryPickupDraft | null) {
    if (!pickupPointDraft) {
        return ""
    }

    return pickupPointDraft.address_full || pickupPointDraft.address
}

function getDoorDeliveryInfoRows(doorDeliveryDraft: DeliveryDoorDraft | null) {
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

function getPickupPointInfoRows(pickupPointDraft: DeliveryPickupDraft | null) {
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

function arePointsClose(
    left: { lat: number; lon: number } | null,
    right: { lat: number; lon: number } | null,
    precision = 0.00005,
) {
    if (!left || !right) {
        return false
    }

    return (
        Math.abs(left.lat - right.lat) <= precision
        && Math.abs(left.lon - right.lon) <= precision
    )
}

export default function DeliveryScreen() {
    const router = useRouter()
    const { width: windowWidth } = useWindowDimensions()
    const isDesktop = windowWidth >= 1100
    const isTablet = windowWidth >= 760
    const selectedDeliveryAddress = useSelectedDeliveryAddress()
    const selectedDeliveryPoint = useSelectedDeliveryPoint()
    const selectedDeliveryCountry = useSelectedDeliveryCountry()
    const activeCountryCode = selectedDeliveryCountry ?? DEFAULT_DELIVERY_COUNTRY_CODE
    const [doorDeliveryDraft, setDoorDeliveryDraft] = useState<DeliveryDoorDraft | null>(
        selectedDeliveryAddress
            ? {
                  ...selectedDeliveryAddress,
                  provider: normalizeDoorDeliveryProvider(selectedDeliveryAddress.provider, activeCountryCode),
              }
            : null,
    )
    const [isDoorFooterExpanded, setIsDoorFooterExpanded] = useState(Boolean(selectedDeliveryAddress))
    const [pickupPointDraft, setPickupPointDraft] = useState<DeliveryPickupDraft | null>(
        selectedDeliveryPoint ? buildPickupPointDraft(selectedDeliveryPoint) : null,
    )
    const [isPickupFooterExpanded, setIsPickupFooterExpanded] = useState(Boolean(selectedDeliveryPoint))
    const [point, setPoint] = useState(DEFAULT_DELIVERY_POINT)
    const [userPoint, setUserPoint] = useState(DEFAULT_DELIVERY_POINT)
    const [searchFocusPoint, setSearchFocusPoint] = useState<typeof DEFAULT_DELIVERY_POINT | null>(null)
    const [hasUserLocation, setHasUserLocation] = useState(false)
    const [isResolvingDoorAddress, setIsResolvingDoorAddress] = useState(false)
    const [isResolvingPickupPoint, setIsResolvingPickupPoint] = useState(false)
    const [removedDeliveryPointKeys, setRemovedDeliveryPointKeys] = useState<Set<string>>(() => new Set())
    const [mapZoom, setMapZoom] = useState(DEFAULT_DELIVERY_ZOOM)
    const [isSearchOpen, setIsSearchOpen] = useState(false)
    const [isSearchFocused, setIsSearchFocused] = useState(false)
    const [search, setSearch] = useState("")
    const [searchEnabled, setSearchEnabled] = useState(true)
    const [selectionError, setSelectionError] = useState<string | null>(null)
    const [pickupPointError, setPickupPointError] = useState<string | null>(null)
    const supportsDoorDelivery = supportsDoorDeliveryForCountry(activeCountryCode)
    const doorDeliveryProviderOptions = useMemo(
        () => getDoorDeliveryProviderOptions(activeCountryCode),
        [activeCountryCode],
    )
    const { deliveryPointMarkers } = useDeliveryPointMarkers(activeCountryCode)
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
    const isSearchActive = isSearchOpen || isSearchFocused
    const hasVisibleSearchFeedback = isLoading || Boolean(error) || results.length > 0
    const shouldFollowUser =
        hasUserLocation && searchFocusPoint === null && doorDeliveryPoint === null && pickupPoint === null
    const shouldShowPickupFooterExtension =
        isPickupFooterExpanded &&
        !hasVisibleSearchFeedback &&
        Boolean(isResolvingPickupPoint || pickupPointDraft || pickupPointError)
    const shouldShowDoorFooterExtension =
        supportsDoorDelivery &&
        isDoorFooterExpanded &&
        !hasVisibleSearchFeedback &&
        Boolean(isResolvingDoorAddress || doorDeliveryDraft || selectionError)
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
                normalizeDoorDeliveryProvider(doorDeliveryDraft?.provider, nextCountryCode),
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
        [activeCountryCode, clearResults, doorDeliveryDraft?.provider],
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

        router.push(ROUTES.home)
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
                    setPickupPointError(getDeliveryCalculationErrorMessage(deliveryCalculationError))
                }
            } else if (provider === "yandex") {
                try {
                    nextDraft.deliveryCalculation = await calculateYandexDelivery(nextDraft.code)
                } catch (deliveryCalculationError) {
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

                setSelectedDeliveryAddress(null)
                setIsDoorFooterExpanded(false)
                setDoorDeliveryDraft(null)
                setSelectedDeliveryPoint(
                    buildSelectedDeliveryPoint(pickupPointDraft, deliveryCalculation),
                )

                router.replace(ROUTES.checkout)
            } catch (deliveryCalculationError) {
                setPickupPointError(getDeliveryCalculationErrorMessage(deliveryCalculationError))
            } finally {
                setIsResolvingPickupPoint(false)
            }
        }

        setIsResolvingPickupPoint(true)
        void choosePickupPoint()
    }, [activeCountryCode, pickupPointDraft, router])

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
                const normalizedProvider = normalizeDoorDeliveryProvider(
                    doorDeliveryDraft.provider,
                    activeCountryCode,
                )
                const deliveryCalculation =
                    doorDeliveryDraft.deliveryCalculation
                    ?? await calculateDoorDelivery({
                        ...doorDeliveryDraft,
                        provider: normalizedProvider,
                    })

                setPickupPointDraft(null)
                setPickupPointError(null)
                setSelectedDeliveryPoint(null)
                setSelectedDeliveryAddress({
                    ...doorDeliveryDraft,
                    provider: normalizedProvider,
                    deliveryCalculation,
                })

                router.replace(ROUTES.checkout)
            } catch (deliveryCalculationError) {
                setSelectionError(getDeliveryCalculationErrorMessage(deliveryCalculationError))
            } finally {
                setIsResolvingDoorAddress(false)
            }
        }

        setIsResolvingDoorAddress(true)
        void chooseDoorDelivery()
    }, [activeCountryCode, doorDeliveryDraft, router])

    const handleSelectDoorDeliveryProvider = useCallback((providerKey: string) => {
        if (!doorDeliveryDraft) {
            return
        }

        const nextProvider = normalizeDoorDeliveryProvider(
            providerKey as DeliveryPointProvider,
            activeCountryCode,
        )

        if (nextProvider === doorDeliveryDraft.provider) {
            return
        }

        const nextDraft: DeliveryDoorDraft = {
            ...doorDeliveryDraft,
            deliveryCalculation: null,
            provider: nextProvider,
        }

        const refreshDoorDeliveryCalculation = async () => {
            try {
                setSelectionError(null)
                setDoorDeliveryDraft(nextDraft)
                const deliveryCalculation = await calculateDoorDelivery(nextDraft)
                setDoorDeliveryDraft({
                    ...nextDraft,
                    deliveryCalculation,
                })
            } catch (deliveryCalculationError) {
                setDoorDeliveryDraft(nextDraft)
                setSelectionError(getDeliveryCalculationErrorMessage(deliveryCalculationError))
            } finally {
                setIsResolvingDoorAddress(false)
            }
        }

        setIsResolvingDoorAddress(true)
        void refreshDoorDeliveryCalculation()
    }, [activeCountryCode, doorDeliveryDraft])

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
                                        isProviderSelectionDisabled={isResolvingDoorAddress}
                                        onChoose={handleChooseDoorDelivery}
                                        onClose={handleCloseDoorFooterExtension}
                                        onCopyInfo={handleCopyPickupInfo}
                                        onSelectProvider={handleSelectDoorDeliveryProvider}
                                        providerOptions={doorDeliveryProviderOptions}
                                        rows={getDoorDeliveryInfoRows(doorDeliveryDraft)}
                                        selectedProviderKey={doorDeliveryDraft?.provider ?? "cdek"}
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
