import { useEffect, useState } from "react"

import {
    DEFAULT_DELIVERY_COUNTRY_CODE,
    getCdekDeliveryPointMarkers,
    getYandexDeliveryPointMarkers,
} from "@/services/api/delivery"
import type {
    DeliveryCountryCode,
    DeliveryPointMarkerWithProvider,
} from "@/services/api/delivery.types"
import type { UseDeliveryPointMarkersState } from "@/hooks/delivery/use-delivery-point-markers.types"

export function useDeliveryPointMarkers(
    countryCode: DeliveryCountryCode | null = DEFAULT_DELIVERY_COUNTRY_CODE,
): UseDeliveryPointMarkersState {
    const [deliveryPointMarkers, setDeliveryPointMarkers] = useState<DeliveryPointMarkerWithProvider[]>([])
    const [isLoading, setIsLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        let isMounted = true

        if (!countryCode) {
            setDeliveryPointMarkers([])
            setError(null)
            setIsLoading(false)

            return () => {
                isMounted = false
            }
        }

        setIsLoading(true)
        setError(null)
        setDeliveryPointMarkers([])

        const markerRequests: Promise<DeliveryPointMarkerWithProvider[]>[] = [
            getCdekDeliveryPointMarkers(countryCode).then((markers) =>
                markers.map((marker) => ({
                    ...marker,
                    provider: "cdek" as const,
                })),
            ),
            ...(countryCode === "RU"
                ? [
                      getYandexDeliveryPointMarkers().then((markers) =>
                          markers.map((marker) => ({
                              ...marker,
                              provider: "yandex" as const,
                          })),
                      ),
                  ]
                : []),
        ]

        void Promise.allSettled(markerRequests)
            .then((results) => {
                if (!isMounted) {
                    return
                }

                const fulfilledMarkers = results.flatMap((result) => {
                    if (result.status !== "fulfilled") {
                        return []
                    }

                    return result.value
                })
                const firstRejectedResult = results.find((result) => result.status === "rejected")

                setDeliveryPointMarkers(fulfilledMarkers)
                setError(
                    fulfilledMarkers.length > 0
                        ? null
                        : firstRejectedResult?.reason instanceof Error
                          ? firstRejectedResult.reason.message
                          : "Failed to load delivery points.",
                )
                setIsLoading(false)
            })
            .catch((deliveryPointError) => {
                if (!isMounted) {
                    return
                }

                setDeliveryPointMarkers([])
                setError(
                    deliveryPointError instanceof Error
                        ? deliveryPointError.message
                        : "Failed to load delivery points.",
                )
                setIsLoading(false)
            })

        return () => {
            isMounted = false
        }
    }, [countryCode])

    return {
        deliveryPointMarkers,
        isLoading,
        error,
    }
}
