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

export function useDeliveryLocation(): DeliveryLocationState {
    const [detectedCountryCode, setDetectedCountryCode] = useState<DeliveryCountryCode | null>(null)
    const [hasUserLocation, setHasUserLocation] = useState(false)
    const [isResolvingLocation, setIsResolvingLocation] = useState(true)
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
            return
        }

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

                hasUserLocationRef.current = true
                setHasUserLocation(true)
                setUserPoint({
                    lat: position.coords.latitude,
                    lon: position.coords.longitude,
                })
                setIsResolvingLocation(false)
            },
        )
    }, [])

    const ensureLocationWatchSafely = useCallback(async () => {
        try {
            await ensureLocationWatch()
        } catch (watchError) {
            console.warn("[delivery] Failed to start user location watch.", watchError)
        }
    }, [ensureLocationWatch])

    const resolveCountryForPoint = useCallback(
        async (nextPoint: InitialRegion) => {
            try {
                const geocodeResult = await reverseGeocodeDeliveryPoint(nextPoint)
                if (!isMountedRef.current) {
                    return
                }

                const nextCountryCode =
                    getSupportedDeliveryCountryCode(geocodeResult.country_code)
                    ?? DEFAULT_DELIVERY_COUNTRY_CODE

                finishCountryResolution(nextCountryCode)
            } catch (error) {
                console.warn("[delivery] Failed to resolve startup country.", error)
                finishCountryResolution(DEFAULT_DELIVERY_COUNTRY_CODE)
            }
        },
        [finishCountryResolution],
    )

    const requestUserLocation = useCallback(async () => {
        try {
            const { status } = await Location.requestForegroundPermissionsAsync()
            if (status !== Location.PermissionStatus.GRANTED) {
                if (!hasUserLocationRef.current) {
                    finishCountryResolution(DEFAULT_DELIVERY_COUNTRY_CODE)
                }

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
                return nextPoint
            }

            const locationServicesEnabled = await Location.hasServicesEnabledAsync()
            if (!locationServicesEnabled) {
                if (!hasUserLocationRef.current) {
                    finishCountryResolution(DEFAULT_DELIVERY_COUNTRY_CODE)
                }

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
                return nextPoint
            } catch {
                void ensureLocationWatchSafely()

                if (!hasUserLocationRef.current) {
                    finishCountryResolution(DEFAULT_DELIVERY_COUNTRY_CODE)
                }

                return null
            }
        } catch (error) {
            console.warn("[delivery] Failed to initialize user location.", error)

            if (!hasUserLocationRef.current) {
                finishCountryResolution(DEFAULT_DELIVERY_COUNTRY_CODE)
            }

            return null
        }
    }, [applyResolvedUserPoint, ensureLocationWatchSafely, finishCountryResolution, resolveCountryForPoint])

    useEffect(() => {
        isMountedRef.current = true
        void requestUserLocation()

        return () => {
            isMountedRef.current = false
            locationSubscriptionRef.current?.remove()
            locationSubscriptionRef.current = null
        }
    }, [requestUserLocation])

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
