import * as Location from "expo-location"
import { useCallback, useEffect, useRef, useState, type RefObject } from "react"
import { Animation, type ClusteredYamap, type InitialRegion } from "react-native-yamap"

import {
    DEFAULT_DELIVERY_POINT,
    DELIVERY_CAMERA_DURATIONS,
    getSupportedDeliveryCountryCode,
} from "@/screens/delivery/delivery-screen.constants"
import type {
    DeliveryCameraCommand,
    DeliveryLocationState,
    DeliveryMapCameraState,
} from "@/screens/delivery/delivery-screen.types"
import type { DeliveryCountryCode } from "@/services/api/delivery.types"
import { DEFAULT_DELIVERY_COUNTRY_CODE, reverseGeocodeDeliveryPoint } from "@/services/api/delivery"
import { logDeliveryFlow } from "@/services/diagnostics/delivery-flow-logger"

const DELIVERY_FLOW_LOG_PREFIX = "[delivery-flow]"

const getLocationLogErrorMessage = (error: unknown) =>
    error instanceof Error ? error.message : "Unknown location error"

export function useDeliveryLocation(): DeliveryLocationState {
    const [detectedCountryCode, setDetectedCountryCode] = useState<DeliveryCountryCode | null>(null)
    const [hasUserLocation, setHasUserLocation] = useState(false)
    const [isResolvingLocation, setIsResolvingLocation] = useState(false)
    const [userPoint, setUserPoint] = useState(DEFAULT_DELIVERY_POINT)
    const hasUserLocationRef = useRef(false)
    const isMountedRef = useRef(true)
    const locationSubscriptionRef = useRef<Location.LocationSubscription | null>(null)

    const applyResolvedUserPoint = useCallback((nextPoint: InitialRegion) => {
        if (!isMountedRef.current) {
            return
        }

        hasUserLocationRef.current = true
        setHasUserLocation(true)
        setUserPoint(nextPoint)
        setIsResolvingLocation(false)
    }, [])

    const finishCountryResolution = useCallback((nextCountryCode: DeliveryCountryCode) => {
        if (!isMountedRef.current) {
            return
        }

        setDetectedCountryCode(nextCountryCode)
        setIsResolvingLocation(false)
    }, [])

    const ensureLocationWatch = useCallback(async () => {
        if (locationSubscriptionRef.current) {
            logDeliveryFlow("location watch already active")
            return
        }

        logDeliveryFlow("location watch start requested")
        locationSubscriptionRef.current = await Location.watchPositionAsync(
            {
                accuracy: Location.Accuracy.Balanced,
                distanceInterval: 10,
                timeInterval: 2_500,
            },
            (position) => {
                if (!isMountedRef.current) {
                    return
                }

                const hadUserLocation = hasUserLocationRef.current
                hasUserLocationRef.current = true
                setHasUserLocation(true)
                setUserPoint({
                    lat: position.coords.latitude,
                    lon: position.coords.longitude,
                })
                setIsResolvingLocation(false)

                if (!hadUserLocation) {
                    logDeliveryFlow("location watch first position received")
                }
            },
        )
        logDeliveryFlow("location watch started")
    }, [])

    const ensureLocationWatchSafely = useCallback(async () => {
        try {
            await ensureLocationWatch()
        } catch (watchError) {
            logDeliveryFlow("location watch failed", {
                error: getLocationLogErrorMessage(watchError),
            })
            console.warn(`${DELIVERY_FLOW_LOG_PREFIX} location watch failed`, {
                error: getLocationLogErrorMessage(watchError),
            })
        }
    }, [ensureLocationWatch])

    const resolveCountryForPoint = useCallback(
        async (nextPoint: InitialRegion) => {
            logDeliveryFlow("location country resolution started")

            try {
                const geocodeResult = await reverseGeocodeDeliveryPoint(nextPoint)
                if (!isMountedRef.current) {
                    logDeliveryFlow("location country resolution ignored after unmount")
                    return
                }

                const nextCountryCode =
                    getSupportedDeliveryCountryCode(geocodeResult.country_code)
                    ?? DEFAULT_DELIVERY_COUNTRY_CODE

                logDeliveryFlow("location country resolved", {
                    countryCode: nextCountryCode,
                })
                finishCountryResolution(nextCountryCode)
            } catch (error) {
                logDeliveryFlow("location country resolution failed", {
                    error: getLocationLogErrorMessage(error),
                })
                console.warn(`${DELIVERY_FLOW_LOG_PREFIX} location country resolution failed`, {
                    error: getLocationLogErrorMessage(error),
                })
                finishCountryResolution(DEFAULT_DELIVERY_COUNTRY_CODE)
            }
        },
        [finishCountryResolution],
    )

    const requestUserLocation = useCallback(async () => {
        logDeliveryFlow("user location request started", {
            hasUserLocation: hasUserLocationRef.current,
        })

        try {
            const { status } = await Location.requestForegroundPermissionsAsync()
            logDeliveryFlow("user location permission result", {
                status,
            })

            if (status !== Location.PermissionStatus.GRANTED) {
                if (!hasUserLocationRef.current) {
                    finishCountryResolution(DEFAULT_DELIVERY_COUNTRY_CODE)
                }

                logDeliveryFlow("user location request denied")
                return null
            }

            const lastKnownPosition = await Location.getLastKnownPositionAsync()
            if (lastKnownPosition) {
                const nextPoint = {
                    lat: lastKnownPosition.coords.latitude,
                    lon: lastKnownPosition.coords.longitude,
                }

                applyResolvedUserPoint(nextPoint)
                void ensureLocationWatchSafely()
                void resolveCountryForPoint(nextPoint)
                logDeliveryFlow("user location resolved from last known position")
                return nextPoint
            }

            const locationServicesEnabled = await Location.hasServicesEnabledAsync()
            if (!locationServicesEnabled) {
                if (!hasUserLocationRef.current) {
                    finishCountryResolution(DEFAULT_DELIVERY_COUNTRY_CODE)
                }

                logDeliveryFlow("user location services disabled")
                return null
            }

            try {
                const currentPosition = await Location.getCurrentPositionAsync({
                    accuracy: Location.Accuracy.Balanced,
                })
                const nextPoint = {
                    lat: currentPosition.coords.latitude,
                    lon: currentPosition.coords.longitude,
                }

                applyResolvedUserPoint(nextPoint)
                void ensureLocationWatchSafely()
                void resolveCountryForPoint(nextPoint)
                logDeliveryFlow("user location resolved from current position")
                return nextPoint
            } catch (currentPositionError) {
                logDeliveryFlow("current user location request failed", {
                    error: getLocationLogErrorMessage(currentPositionError),
                })
                console.warn(`${DELIVERY_FLOW_LOG_PREFIX} current user location request failed`, {
                    error: getLocationLogErrorMessage(currentPositionError),
                })
                void ensureLocationWatchSafely()

                if (!hasUserLocationRef.current) {
                    finishCountryResolution(DEFAULT_DELIVERY_COUNTRY_CODE)
                }

                return null
            }
        } catch (error) {
            logDeliveryFlow("user location request failed", {
                error: getLocationLogErrorMessage(error),
            })
            console.warn(`${DELIVERY_FLOW_LOG_PREFIX} user location request failed`, {
                error: getLocationLogErrorMessage(error),
            })

            if (!hasUserLocationRef.current) {
                finishCountryResolution(DEFAULT_DELIVERY_COUNTRY_CODE)
            }

            return null
        }
    }, [applyResolvedUserPoint, ensureLocationWatchSafely, finishCountryResolution, resolveCountryForPoint])

    useEffect(() => {
        isMountedRef.current = true
        logDeliveryFlow("location hook mounted", {
            passiveStartupDisabled: true,
        })

        return () => {
            logDeliveryFlow("location hook unmounted", {
                hadLocationWatch: Boolean(locationSubscriptionRef.current),
            })
            isMountedRef.current = false
            locationSubscriptionRef.current?.remove()
            locationSubscriptionRef.current = null
        }
    }, [])

    return {
        detectedCountryCode,
        hasUserLocation,
        isResolvingLocation,
        requestUserLocation,
        userPoint,
    }
}

export function useDeliveryMapCamera(
    mapRef: RefObject<ClusteredYamap | null>,
): DeliveryMapCameraState {
    const appliedCommandIdRef = useRef<number | null>(null)
    const nextCommandIdRef = useRef(0)
    const pendingCommandRef = useRef<DeliveryCameraCommand | null>(null)

    const applyCameraCommand = useCallback(
        (cameraCommand: DeliveryCameraCommand) => {
            if (!mapRef.current) {
                pendingCommandRef.current = cameraCommand
                return false
            }

            if (appliedCommandIdRef.current === cameraCommand.id) {
                pendingCommandRef.current = null
                return true
            }

            mapRef.current.setCenter(
                cameraCommand.region,
                cameraCommand.region.zoom,
                cameraCommand.region.azimuth,
                cameraCommand.region.tilt,
                cameraCommand.duration,
                Animation.SMOOTH,
            )
            appliedCommandIdRef.current = cameraCommand.id
            pendingCommandRef.current = null
            return true
        },
        [mapRef],
    )

    const moveToRegion = useCallback(
        (region: InitialRegion, duration: number = DELIVERY_CAMERA_DURATIONS.search) => {
            nextCommandIdRef.current += 1
            applyCameraCommand({
                duration,
                id: nextCommandIdRef.current,
                kind: "region",
                region,
            })
        },
        [applyCameraCommand],
    )

    const handleMapLoaded = useCallback(() => {
        const pendingCommand = pendingCommandRef.current
        if (!pendingCommand) {
            return
        }

        applyCameraCommand(pendingCommand)
    }, [applyCameraCommand])

    return {
        handleMapLoaded,
        moveToRegion,
    }
}
