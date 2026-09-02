import { useSyncExternalStore } from "react"
import { Platform } from "react-native"

// Fail closed on iOS until the backend policy arrives. There is no local switch.
let catalogAvailable = Platform.OS !== "ios"
const listeners = new Set<() => void>()
const subscribe = (listener: () => void) => {
    listeners.add(listener)
    return () => { listeners.delete(listener) }
}

export function applyAppFeaturePolicy(appleDevMode: unknown) {
    const next = Platform.OS !== "ios" || appleDevMode === false
    if (next === catalogAvailable) return
    catalogAvailable = next
    listeners.forEach((listener) => listener())
}

export const isCatalogAvailable = () => catalogAvailable
export const useCatalogAvailable = () => useSyncExternalStore(subscribe, isCatalogAvailable, isCatalogAvailable)

export function isCatalogRoute(path: string) {
    const normalized = path.split(/[?#]/)[0].replace(/\/+$/, "") || "/"
    return ["/discover", "/basket", "/checkout", "/payment", "/favorites", "/profile-drafts", "/profile-discounts"]
        .includes(normalized) || normalized === "/products" || normalized.startsWith("/products/")
}
