import { useCallback, useEffect, useRef, useState } from "react"
import type { Dispatch, SetStateAction } from "react"

import { getErrorMessage } from "@/utils/errors"

type ReloadOptions = {
    showLoading?: boolean
}

type UseAsyncDataOptions<TData> = {
    debounceMs?: number
    deps: readonly unknown[]
    enabled?: boolean
    fetcher: () => Promise<TData>
    initialData: TData
    resetOnLoad?: boolean
}

export function useAsyncData<TData>({
    debounceMs = 0,
    deps,
    enabled = true,
    fetcher,
    initialData,
    resetOnLoad = false,
}: UseAsyncDataOptions<TData>) {
    const [data, setData] = useState(initialData)
    const [loading, setLoading] = useState(enabled)
    const [error, setError] = useState<string | null>(null)
    const depsKey = JSON.stringify(deps)
    const fetcherRef = useRef(fetcher)
    const initialDataRef = useRef(initialData)
    const requestIdRef = useRef(0)

    fetcherRef.current = fetcher

    const reset = useCallback(() => {
        requestIdRef.current += 1
        setData(initialDataRef.current)
        setLoading(false)
        setError(null)
    }, [])

    const reload = useCallback(async ({ showLoading = true }: ReloadOptions = {}) => {
        const requestId = requestIdRef.current + 1
        requestIdRef.current = requestId

        if (showLoading) {
            setLoading(true)
        }

        if (resetOnLoad) {
            setData(initialDataRef.current)
        }

        setError(null)

        try {
            const nextData = await fetcherRef.current()

            if (requestIdRef.current !== requestId) {
                return null
            }

            setData(nextData)
            return nextData
        } catch (loadError) {
            if (requestIdRef.current !== requestId) {
                return null
            }

            setData(initialDataRef.current)
            setError(getErrorMessage(loadError))
            return null
        } finally {
            if (requestIdRef.current === requestId) {
                setLoading(false)
            }
        }
    }, [resetOnLoad])

    useEffect(() => {
        if (!enabled) {
            reset()
            return
        }

        if (debounceMs > 0) {
            setLoading(true)
            setError(null)

            const timeoutId = setTimeout(() => {
                void reload({ showLoading: false })
            }, debounceMs)

            return () => {
                clearTimeout(timeoutId)
                requestIdRef.current += 1
            }
        }

        void reload()
    }, [debounceMs, depsKey, enabled, reload, reset])

    return {
        data,
        error,
        loading,
        reload,
        setData: setData as Dispatch<SetStateAction<TData>>,
    }
}
