import { useCallback, useEffect, useState } from "react"
import { Dimensions, Keyboard, Platform, type KeyboardMetrics, type LayoutChangeEvent } from "react-native"

export function androidDockOverlap(viewportHeight: number, screenHeight: number, navInset: number, ime: KeyboardMetrics | undefined) {
    if (!ime || ime.height <= 0) return 0
    // Edge-to-edge may leave the map full height; older windows can already be resized.
    const imeTop = Math.min(ime.screenY, screenHeight - ime.height - navInset)
    return Math.max(0, viewportHeight - Math.max(0, imeTop))
}

export function useAndroidDeliveryDock(navInset: number) {
    const [viewportHeight, setViewportHeight] = useState(0)
    const [ime, setIme] = useState<KeyboardMetrics>()
    const onLayout = useCallback((event: LayoutChangeEvent) => {
        setViewportHeight(event.nativeEvent.layout.height)
    }, [])
    useEffect(() => {
        if (Platform.OS !== "android") return
        setIme(Keyboard.metrics())
        const show = Keyboard.addListener("keyboardDidShow", e => setIme(e.endCoordinates))
        const hide = Keyboard.addListener("keyboardDidHide", () => setIme(undefined))
        return () => { show.remove(); hide.remove() }
    }, [])
    return {
        onLayout: Platform.OS === "android" ? onLayout : undefined,
        bottom: Platform.OS === "android"
            ? androidDockOverlap(viewportHeight, Dimensions.get("screen").height, navInset, ime) : 0,
    }
}
