import { useEffect, useState } from "react"

import {
    DEFAULT_DELIVERY_COUNTRY_CODE,
    getCdekDeliveryPointMarkers,
    getYandexDeliveryPointMarkers,
} from "@/services/api/delivery"
import type {
    DeliveryCountryCode,
    DeliveryPointProvider,
    DeliveryPointMarkerWithProvider,
} from "@/services/api/delivery.types"
import type { UseDeliveryPointMarkersState } from "@/hooks/delivery/use-delivery-point-markers.types"
import { logDeliveryFlow } from "@/services/diagnostics/delivery-flow-logger"

const DELIVERY_FLOW_LOG_PREFIX = "[delivery-flow]"

const getMarkerLoadErrorMessage = (error: unknown) =>
    error instanceof Error ? error.message : "Unknown marker load error"

export function useDeliveryPointMarkers(
    countryCode: DeliveryCountryCode | null = DEFAULT_DELIVERY_COUNTRY_CODE,
    options: {
        enabled?: boolean
    } = {},
): UseDeliveryPointMarkersState {
    const { enabled = true } = options
    const [deliveryPointMarkers, setDeliveryPointMarkers] = useState<DeliveryPointMarkerWithProvider[]>([])
    const [isLoading, setIsLoading] = useState(Boolean(enabled && countryCode))
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        let isMounted = true

        if (!enabled || !countryCode) {
            logDeliveryFlow("pickup markers disabled", {
                countryCode,
                enabled,
            })
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

        const startedAt = Date.now()
        logDeliveryFlow("pickup marker load started", {
            countryCode,
        })

        const trackProviderRequest = (
            provider: DeliveryPointProvider,
            request: Promise<DeliveryPointMarkerWithProvider[]>,
        ) => {
            const providerStartedAt = Date.now()
            logDeliveryFlow("pickup marker provider request started", {
                countryCode,
                provider,
            })

            return request
                .then((markers) => {
                    logDeliveryFlow("pickup marker provider request finished", {
                        countryCode,
                        durationMs: Date.now() - providerStartedAt,
                        markerCount: markers.length,
                        provider,
                    })

                    return markers
                })
                .catch((providerError) => {
                    logDeliveryFlow("pickup marker provider request failed", {
                        countryCode,
                        durationMs: Date.now() - providerStartedAt,
                        error: getMarkerLoadErrorMessage(providerError),
                        provider,
                    })

                    throw providerError
                })
        }

        const markerRequests: {
            provider: DeliveryPointProvider
            request: Promise<DeliveryPointMarkerWithProvider[]>
        }[] = [
            {
                provider: "cdek",
                request: trackProviderRequest(
                    "cdek",
                    getCdekDeliveryPointMarkers(countryCode).then((markers) =>
                        markers.map((marker) => ({
                            ...marker,
                            provider: "cdek" as const,
                        })),
                    ),
                ),
            },
            ...(countryCode === "RU"
                ? [
                      {
                          provider: "yandex" as const,
                          request: trackProviderRequest(
                              "yandex",
                              getYandexDeliveryPointMarkers().then((markers) =>
                                  markers.map((marker) => ({
                                      ...marker,
                                      provider: "yandex" as const,
                                  })),
                              ),
                          ),
                      },
                  ]
                : []),
        ]

        void Promise.allSettled(markerRequests.map(({ request }) => request))
            .then((results) => {
                if (!isMounted) {
                    logDeliveryFlow("pickup marker load ignored after unmount", {
                        countryCode,
                        durationMs: Date.now() - startedAt,
                    })
                    return
                }

                const fulfilledMarkers = results.flatMap((result) => {
                    if (result.status !== "fulfilled") {
                        return []
                    }

                    return result.value
                })
                const firstRejectedResult = results.find((result) => result.status === "rejected")
                const providerCounts = results.reduce<Record<string, number>>((counts, result, index) => {
                    const provider = markerRequests[index]?.provider ?? "unknown"
                    counts[provider] = result.status === "fulfilled" ? result.value.length : 0
                    return counts
                }, {})
                const rejectedProviders = results.flatMap((result, index) =>
                    result.status === "rejected"
                        ? [markerRequests[index]?.provider ?? "unknown"]
                        : [],
                )

                logDeliveryFlow("pickup marker load settled", {
                    countryCode,
                    durationMs: Date.now() - startedAt,
                    providerCounts,
                    rejectedProviders,
                    totalCount: fulfilledMarkers.length,
                })

                if (firstRejectedResult?.status === "rejected") {
                    logDeliveryFlow("pickup marker provider failed", {
                        countryCode,
                        error: getMarkerLoadErrorMessage(firstRejectedResult.reason),
                    })
                }

                logDeliveryFlow("pickup marker state commit queued", {
                    countryCode,
                    providerCounts,
                    totalCount: fulfilledMarkers.length,
                })
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
                    logDeliveryFlow("pickup marker load error ignored after unmount", {
                        countryCode,
                        durationMs: Date.now() - startedAt,
                    })
                    return
                }

                logDeliveryFlow("pickup marker load failed", {
                    countryCode,
                    durationMs: Date.now() - startedAt,
                    error: getMarkerLoadErrorMessage(deliveryPointError),
                })
                console.error(`${DELIVERY_FLOW_LOG_PREFIX} pickup marker load failed`, {
                    countryCode,
                    durationMs: Date.now() - startedAt,
                    error: getMarkerLoadErrorMessage(deliveryPointError),
                })
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
    }, [countryCode, enabled])

    return {
        deliveryPointMarkers,
        isLoading,
        error,
    }
}
