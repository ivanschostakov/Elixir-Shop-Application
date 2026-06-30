import { Platform } from "react-native"

type TelegramWebAppContactCallback = (isShared: boolean) => void
type TelegramWebAppEvent =
    | "viewportChanged"
    | "safeAreaChanged"
    | "contentSafeAreaChanged"
    | "themeChanged"

type TelegramWebAppEventCallback = () => void

export type TelegramWebAppInset = {
    bottom: number
    left: number
    right: number
    top: number
}

export type TelegramViewportSnapshot = {
    contentSafeAreaInset: TelegramWebAppInset
    safeAreaInset: TelegramWebAppInset
    viewportHeight: number | null
    viewportStableHeight: number | null
}

export type TelegramWebApp = {
    backgroundColor?: string
    contentSafeAreaInset?: Partial<TelegramWebAppInset>
    initData: string
    isExpanded?: boolean
    safeAreaInset?: Partial<TelegramWebAppInset>
    viewportHeight?: number
    viewportStableHeight?: number
    colorScheme?: "light" | "dark"
    ready?: () => void
    expand?: () => void
    close?: () => void
    disableVerticalSwipes?: () => void
    offEvent?: (eventType: TelegramWebAppEvent, eventHandler: TelegramWebAppEventCallback) => void
    onEvent?: (eventType: TelegramWebAppEvent, eventHandler: TelegramWebAppEventCallback) => void
    requestContact?: (callback?: TelegramWebAppContactCallback) => void
    setBackgroundColor?: (color: string) => void
    setBottomBarColor?: (color: string) => void
    setHeaderColor?: (color: string) => void
}

type TelegramWindow = Window & {
    Telegram?: {
        WebApp?: TelegramWebApp
    }
}

function getTelegramWindow(): TelegramWindow | null {
    if (Platform.OS !== "web" || typeof window === "undefined") {
        return null
    }

    return window as TelegramWindow
}

export function getTelegramWebApp(): TelegramWebApp | null {
    return getTelegramWindow()?.Telegram?.WebApp ?? null
}

export function getTelegramInitData(): string {
    return getTelegramWebApp()?.initData?.trim() ?? ""
}

export function isTelegramWebAppEnvironment(): boolean {
    return Boolean(getTelegramInitData())
}

const ZERO_INSET: TelegramWebAppInset = {
    bottom: 0,
    left: 0,
    right: 0,
    top: 0,
}

function numberOrZero(value: unknown) {
    return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : 0
}

function normalizeInset(inset: Partial<TelegramWebAppInset> | undefined): TelegramWebAppInset {
    if (!inset) {
        return ZERO_INSET
    }

    return {
        bottom: numberOrZero(inset.bottom),
        left: numberOrZero(inset.left),
        right: numberOrZero(inset.right),
        top: numberOrZero(inset.top),
    }
}

function numberOrNull(value: unknown) {
    return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : null
}

export function getTelegramViewportSnapshot(): TelegramViewportSnapshot {
    const webApp = getTelegramWebApp()

    return {
        contentSafeAreaInset: normalizeInset(webApp?.contentSafeAreaInset),
        safeAreaInset: normalizeInset(webApp?.safeAreaInset),
        viewportHeight: numberOrNull(webApp?.viewportHeight),
        viewportStableHeight: numberOrNull(webApp?.viewportStableHeight),
    }
}

function setCssVariable(name: string, value: number | null) {
    if (typeof document === "undefined") {
        return
    }

    document.documentElement.style.setProperty(name, value ? `${value}px` : "0px")
}

export function applyTelegramViewportStyles() {
    if (typeof document === "undefined" || typeof window === "undefined") {
        return
    }

    const snapshot = getTelegramViewportSnapshot()
    const visualViewportHeight =
        typeof window.visualViewport?.height === "number" ? window.visualViewport.height : null
    const fallbackViewportHeight = visualViewportHeight ?? window.innerHeight
    const viewportHeight = snapshot.viewportHeight ?? fallbackViewportHeight
    const viewportStableHeight = snapshot.viewportStableHeight ?? viewportHeight

    document.documentElement.style.setProperty("--telegram-viewport-height", `${viewportHeight}px`)
    document.documentElement.style.setProperty("--telegram-viewport-stable-height", `${viewportStableHeight}px`)

    setCssVariable("--telegram-safe-area-inset-top", snapshot.safeAreaInset.top)
    setCssVariable("--telegram-safe-area-inset-right", snapshot.safeAreaInset.right)
    setCssVariable("--telegram-safe-area-inset-bottom", snapshot.safeAreaInset.bottom)
    setCssVariable("--telegram-safe-area-inset-left", snapshot.safeAreaInset.left)
    setCssVariable("--telegram-content-safe-area-inset-top", snapshot.contentSafeAreaInset.top)
    setCssVariable("--telegram-content-safe-area-inset-right", snapshot.contentSafeAreaInset.right)
    setCssVariable("--telegram-content-safe-area-inset-bottom", snapshot.contentSafeAreaInset.bottom)
    setCssVariable("--telegram-content-safe-area-inset-left", snapshot.contentSafeAreaInset.left)

    document.documentElement.style.height = "var(--telegram-viewport-height)"
    document.body.style.height = "var(--telegram-viewport-height)"
    document.body.style.overflow = "hidden"
    document.body.style.overscrollBehavior = "none"
}

export function subscribeTelegramViewportChanges(callback: (snapshot: TelegramViewportSnapshot) => void) {
    if (Platform.OS !== "web" || typeof window === "undefined") {
        return () => undefined
    }

    const webApp = getTelegramWebApp()
    const handleChange = () => {
        applyTelegramViewportStyles()
        callback(getTelegramViewportSnapshot())
    }
    const events: TelegramWebAppEvent[] = ["viewportChanged", "safeAreaChanged", "contentSafeAreaChanged"]

    handleChange()
    window.visualViewport?.addEventListener("resize", handleChange)
    window.addEventListener("resize", handleChange)

    for (const event of events) {
        webApp?.onEvent?.(event, handleChange)
    }

    return () => {
        window.visualViewport?.removeEventListener("resize", handleChange)
        window.removeEventListener("resize", handleChange)

        for (const event of events) {
            webApp?.offEvent?.(event, handleChange)
        }
    }
}

export function setTelegramChromeColors({
    backgroundColor,
    bottomBarColor,
    headerColor,
}: {
    backgroundColor?: string
    bottomBarColor?: string
    headerColor?: string
}) {
    const webApp = getTelegramWebApp()

    try {
        if (backgroundColor) {
            webApp?.setBackgroundColor?.(backgroundColor)
        }
        if (bottomBarColor) {
            webApp?.setBottomBarColor?.(bottomBarColor)
        }
        if (headerColor) {
            webApp?.setHeaderColor?.(headerColor)
        }
    } catch {
        // Older Telegram clients may expose a partial WebApp API.
    }
}

export function initializeTelegramWebApp() {
    const webApp = getTelegramWebApp()
    if (!webApp) {
        return
    }

    webApp.ready?.()
    webApp.expand?.()
    webApp.disableVerticalSwipes?.()
    setTelegramChromeColors({
        backgroundColor: "#F3F5F8",
        bottomBarColor: "#FFFFFF",
        headerColor: "#0A84FF",
    })
    applyTelegramViewportStyles()
}

export function requestTelegramContact(): Promise<boolean> {
    const webApp = getTelegramWebApp()
    const requestContact = webApp?.requestContact
    if (!requestContact) {
        return Promise.resolve(false)
    }

    return new Promise((resolve) => {
        try {
            requestContact((isShared) => {
                resolve(Boolean(isShared))
            })
        } catch {
            resolve(false)
        }
    })
}
