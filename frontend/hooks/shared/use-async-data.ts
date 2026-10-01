import { useCallback, useEffect, useRef, useState } from "react"
import type { Dispatch, SetStateAction } from "react"

import { getErrorMessage, showBackendErrorAlert } from "@/utils/errors"

type ReloadOptions = { showLoading?: boolean }
type UseAsyncDataOptions<TData> = {
    debounceMs?: number
    deps: readonly unknown[]
    enabled?: boolean
    fetcher: () => Promise<TData>
    initialData: TData
    resetOnLoad?: boolean
    preserveDataOnError?: boolean
}

export function useAsyncData<TData>({ debounceMs = 0, deps, enabled = true, fetcher, initialData, resetOnLoad = false, preserveDataOnError = true }: UseAsyncDataOptions<TData>) {
    const scope = JSON.stringify(deps)
    const [snapshot, setSnapshot] = useState({ scope, data: initialData, loaded: false })
    const [request, setRequest] = useState({ scope, loading: enabled, error: null as string | null })
    const snapshotRef = useRef(snapshot)
    const scopeRef = useRef(scope)
    const fetcherRef = useRef(fetcher)
    const initialDataRef = useRef(initialData)
    const requestIdRef = useRef(0)
    snapshotRef.current = snapshot
    scopeRef.current = scope
    fetcherRef.current = fetcher

    const reset = useCallback(() => {
        requestIdRef.current += 1
        const key = scopeRef.current
        setSnapshot({ scope: key, data: initialDataRef.current, loaded: false })
        setRequest({ scope: key, loading: false, error: null })
    }, [])

    const setData = useCallback<Dispatch<SetStateAction<TData>>>((value) => {
        if (scopeRef.current !== scope) return
        const key = scope
        setSnapshot(previous => ({
            scope: key,
            loaded: true,
            data: typeof value === "function" ? (value as (previous: TData) => TData)(previous.scope === key ? previous.data : initialDataRef.current) : value,
        }))
    }, [scope])

    const reload = useCallback(async ({ showLoading = true }: ReloadOptions = {}) => {
        if (scopeRef.current !== scope) return null
        const requestId = ++requestIdRef.current
        const cached = snapshotRef.current.scope === scope && snapshotRef.current.loaded
        // Refreshes keep the current layout. Dependency changes never expose another scope's data.
        setRequest({ scope, loading: showLoading && !cached, error: null })
        if (resetOnLoad && !cached) setSnapshot({ scope, data: initialDataRef.current, loaded: false })
        const isCurrent = () => requestIdRef.current === requestId && scopeRef.current === scope
        try {
            const nextData = await fetcherRef.current()
            if (!isCurrent()) return null
            setSnapshot({ scope, data: nextData, loaded: true })
            return nextData
        } catch (loadError) {
            if (!isCurrent()) return null
            if (!preserveDataOnError) setSnapshot({ scope, data: initialDataRef.current, loaded: false })
            setRequest({ scope, loading: false, error: getErrorMessage(loadError) })
            showBackendErrorAlert(loadError)
            return null
        } finally {
            if (isCurrent()) setRequest(previous => ({ ...previous, loading: false }))
        }
    }, [preserveDataOnError, resetOnLoad, scope])

    useEffect(() => {
        if (!enabled) { reset(); return }
        if (debounceMs > 0) {
            const cached = snapshotRef.current.scope === scope && snapshotRef.current.loaded
            setRequest({ scope, loading: !cached, error: null })
            const timeoutId = setTimeout(() => { void reload() }, debounceMs)
            return () => { clearTimeout(timeoutId); requestIdRef.current += 1 }
        }
        void reload()
        return () => { requestIdRef.current += 1 }
    }, [debounceMs, scope, enabled, reload, reset])

    return {
        data: snapshot.scope === scope ? snapshot.data : initialDataRef.current,
        error: request.scope === scope ? request.error : null,
        loading: request.scope === scope ? request.loading : enabled,
        reload,
        setData,
    }
}
