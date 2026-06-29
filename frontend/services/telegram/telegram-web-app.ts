import { Platform } from "react-native"

type TelegramWebAppContactCallback = (isShared: boolean) => void

export type TelegramWebApp = {
    initData: string
    colorScheme?: "light" | "dark"
    ready?: () => void
    expand?: () => void
    close?: () => void
    disableVerticalSwipes?: () => void
    requestContact?: (callback?: TelegramWebAppContactCallback) => void
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

export function initializeTelegramWebApp() {
    const webApp = getTelegramWebApp()
    if (!webApp) {
        return
    }

    webApp.ready?.()
    webApp.expand?.()
    webApp.disableVerticalSwipes?.()

    if (typeof document !== "undefined") {
        document.documentElement.style.height = "100%"
        document.body.style.height = "100%"
        document.body.style.overflow = "hidden"
    }
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
