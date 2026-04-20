import { useCallback } from "react"

import { useAsyncData } from "@/hooks/shared/use-async-data"
import { suggestDeliveryGeo } from "@/services/api/delivery"
import type { DeliveryGeoPoint, DeliveryGeoSuggestResult } from "@/services/api/delivery.types"

export function useDeliveryGeoSearch(
    query: string,
    point: DeliveryGeoPoint,
    enabled = true,
) {
    const normalizedQuery = query.trim()
    const isEnabled = enabled && normalizedQuery.length > 0
    const { data, error, loading, reload, setData } = useAsyncData<DeliveryGeoSuggestResult[]>({
        debounceMs: 300,
        deps: [normalizedQuery, point.lat, point.lon],
        enabled: isEnabled,
        fetcher: () => suggestDeliveryGeo(normalizedQuery, point),
        initialData: [],
        resetOnLoad: true,
    })

    const clearResults = useCallback(() => {
        setData([])
    }, [setData])

    const runSearch = useCallback(async () => {
        if (!normalizedQuery.length) {
            setData([])
            return []
        }

        return (await reload()) ?? []
    }, [normalizedQuery.length, reload, setData])

    return {
        clearResults,
        error,
        isLoading: loading,
        results: data,
        runSearch,
    }
}
