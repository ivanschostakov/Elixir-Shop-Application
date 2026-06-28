import { useCallback, useEffect, useRef, useState } from "react"

import { getErrorMessage, showBackendErrorAlert } from "@/utils/errors"

type LoadPageArgs = {
    limit: number
    offset: number
}

type ReloadOptions = {
    showLoading?: boolean
    resetItems?: boolean
}

type UsePaginatedDataOptions<TItem> = {
    deps: readonly unknown[]
    enabled?: boolean
    fetchPage: (args: LoadPageArgs) => Promise<TItem[]>
    getKey?: (item: TItem) => number | string
    pageSize: number
}

export function usePaginatedData<TItem>({
    deps,
    enabled = true,
    fetchPage,
    getKey,
    pageSize,
}: UsePaginatedDataOptions<TItem>) {
    const [items, setItems] = useState<TItem[]>([])
    const [loading, setLoading] = useState(false)
    const [loadingMore, setLoadingMore] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [hasMore, setHasMore] = useState(true)
    const depsKey = JSON.stringify(deps)
    const fetchPageRef = useRef(fetchPage)
    const itemsRef = useRef<TItem[]>([])
    const requestIdRef = useRef(0)

    fetchPageRef.current = fetchPage

    useEffect(() => {
        itemsRef.current = items
    }, [items])

    const reset = useCallback(() => {
        requestIdRef.current += 1
        itemsRef.current = []
        setItems([])
        setLoading(false)
        setLoadingMore(false)
        setError(null)
        setHasMore(true)
    }, [])

    const reload = useCallback(async ({
        showLoading = true,
        resetItems = true,
    }: ReloadOptions = {}) => {
        const requestId = requestIdRef.current + 1
        requestIdRef.current = requestId

        if (resetItems) {
            itemsRef.current = []
            setItems([])
        }

        if (showLoading) {
            setLoading(true)
        }

        setLoadingMore(false)
        setError(null)
        setHasMore(true)

        try {
            const nextItems = await fetchPageRef.current({
                limit: pageSize,
                offset: 0,
            })

            if (requestIdRef.current !== requestId) {
                return null
            }

            itemsRef.current = nextItems
            setItems(nextItems)
            setHasMore(nextItems.length === pageSize)
            return nextItems
        } catch (loadError) {
            if (requestIdRef.current !== requestId) {
                return null
            }

            if (resetItems) {
                itemsRef.current = []
                setItems([])
            }

            setError(getErrorMessage(loadError))
            showBackendErrorAlert(loadError)
            setHasMore(false)
            return null
        } finally {
            if (requestIdRef.current === requestId) {
                setLoading(false)
            }
        }
    }, [pageSize])

    useEffect(() => {
        if (!enabled) {
            reset()
            return
        }

        void reload()
    }, [depsKey, enabled, reload, reset])

    const loadMore = useCallback(async () => {
        if (!enabled || loading || loadingMore || !hasMore) {
            return null
        }

        const requestId = requestIdRef.current
        setLoadingMore(true)
        setError(null)

        try {
            const nextItems = await fetchPageRef.current({
                limit: pageSize,
                offset: itemsRef.current.length,
            })

            if (requestIdRef.current !== requestId) {
                return null
            }

            const mergedItems = getKey
                ? [...itemsRef.current, ...nextItems].filter((item, index, allItems) => {
                      const itemKey = getKey(item)
                      return allItems.findIndex((currentItem) => getKey(currentItem) === itemKey) === index
                  })
                : [...itemsRef.current, ...nextItems]

            itemsRef.current = mergedItems
            setItems(mergedItems)
            setHasMore(nextItems.length === pageSize)
            return nextItems
        } catch (loadError) {
            if (requestIdRef.current !== requestId) {
                return null
            }

            setError(getErrorMessage(loadError))
            showBackendErrorAlert(loadError)
            return null
        } finally {
            if (requestIdRef.current === requestId) {
                setLoadingMore(false)
            }
        }
    }, [enabled, getKey, hasMore, loading, loadingMore, pageSize])

    return {
        error,
        hasMore,
        items,
        loadMore,
        loading,
        loadingMore,
        reload,
        setItems,
    }
}
