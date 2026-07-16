import { useCallback, useEffect, useMemo, useState } from "react"
import * as SecureStore from "expo-secure-store"
import { Appearance, Platform } from "react-native"

import { ThemeContext } from "@/providers/theme-provider.context"
import type { ThemeProviderProps } from "@/providers/theme-provider.types"
import {
    applyWebThemeColors,
    darkColors,
    darkBlackWhiteAccentPalette,
    lightColors,
    themeAccentPalettes,
    type ThemeAccentName,
    type ThemeName,
} from "@/theme/colors"

const THEME_STORAGE_KEY = "elixirpeptide-theme"
const THEME_ACCENT_STORAGE_KEY = "elixirpeptide-theme-accent"
type StoredThemeAccentName = ThemeAccentName | "blue"

function isThemeName(value: string | null): value is ThemeName {
    return value === "light" || value === "dark"
}

function isThemeAccentName(value: string | null): value is StoredThemeAccentName {
    return (
        value === "vividBlue" ||
        value === "archivedBlue" ||
        value === "teal" ||
        value === "emerald" ||
        value === "rose" ||
        value === "amber" ||
        value === "blackWhite" ||
        value === "blue"
    )
}

function normalizeThemeAccentName(value: string | null): ThemeAccentName | null {
    if (!isThemeAccentName(value)) {
        return null
    }

    if (value === "blue") {
        return "archivedBlue"
    }

    return value
}

function getWebStorage() {
    if (typeof window === "undefined" || typeof window.localStorage === "undefined") {
        return null
    }

    return window.localStorage
}

async function readStoredTheme(): Promise<ThemeName | null> {
    if (Platform.OS === "web") {
        const storedThemeName = getWebStorage()?.getItem(THEME_STORAGE_KEY) ?? null
        return isThemeName(storedThemeName) ? storedThemeName : null
    }

    try {
        const storedThemeName = await SecureStore.getItemAsync(THEME_STORAGE_KEY)
        return isThemeName(storedThemeName) ? storedThemeName : null
    } catch {
        return null
    }
}

async function persistTheme(themeName: ThemeName) {
    if (Platform.OS === "web") {
        getWebStorage()?.setItem(THEME_STORAGE_KEY, themeName)
        return
    }

    try {
        await SecureStore.setItemAsync(THEME_STORAGE_KEY, themeName)
    } catch {
        // The visible theme still changes even if local persistence fails.
    }
}

async function readStoredAccent(): Promise<ThemeAccentName | null> {
    if (Platform.OS === "web") {
        const storedAccentName = getWebStorage()?.getItem(THEME_ACCENT_STORAGE_KEY) ?? null
        return normalizeThemeAccentName(storedAccentName)
    }

    try {
        const storedAccentName = await SecureStore.getItemAsync(THEME_ACCENT_STORAGE_KEY)
        return normalizeThemeAccentName(storedAccentName)
    } catch {
        return null
    }
}

async function persistAccent(accentName: ThemeAccentName) {
    if (Platform.OS === "web") {
        getWebStorage()?.setItem(THEME_ACCENT_STORAGE_KEY, accentName)
        return
    }

    try {
        await SecureStore.setItemAsync(THEME_ACCENT_STORAGE_KEY, accentName)
    } catch {
        // The visible accent still changes even if local persistence fails.
    }
}

function applyTheme(themeName: ThemeName) {
    Appearance.setColorScheme?.(themeName)
    applyWebThemeColors(themeName)
}

function getSystemThemeName(): ThemeName {
    return Appearance.getColorScheme() === "dark" ? "dark" : "light"
}

function getInitialThemeName(): ThemeName {
    if (Platform.OS !== "web") {
        return getSystemThemeName()
    }

    const storedThemeName = getWebStorage()?.getItem(THEME_STORAGE_KEY) ?? null
    const initialThemeName = isThemeName(storedThemeName) ? storedThemeName : getSystemThemeName()
    applyWebThemeColors(initialThemeName)
    return initialThemeName
}

export function ThemeProvider({ children }: ThemeProviderProps) {
    const [themeName, setThemeName] = useState<ThemeName>(getInitialThemeName)
    const [accentName, setAccentNameState] = useState<ThemeAccentName>("vividBlue")

    useEffect(() => {
        applyTheme(themeName)
    }, [themeName])

    useEffect(() => {
        let isMounted = true

        void readStoredTheme().then((storedThemeName) => {
            if (!isMounted) {
                return
            }

            if (!storedThemeName) {
                return
            }

            setThemeName(storedThemeName)
        })

        return () => {
            isMounted = false
        }
    }, [])

    useEffect(() => {
        let isMounted = true

        void readStoredAccent().then((storedAccentName) => {
            if (!isMounted || !storedAccentName) {
                return
            }

            setAccentNameState(storedAccentName)
        })

        return () => {
            isMounted = false
        }
    }, [])

    const toggleTheme = useCallback(() => {
        const nextThemeName = themeName === "dark" ? "light" : "dark"
        applyTheme(nextThemeName)
        setThemeName(nextThemeName)
        void persistTheme(nextThemeName)
    }, [themeName])

    const setAccentName = useCallback((nextAccentName: ThemeAccentName) => {
        setAccentNameState(nextAccentName)
        void persistAccent(nextAccentName)
    }, [])

    const value = useMemo(
        () => ({
            isDark: themeName === "dark",
            palette: themeName === "dark" ? darkColors : lightColors,
            themeName,
            accentName,
            accentPalette: accentName === "blackWhite" && themeName === "dark"
                ? darkBlackWhiteAccentPalette
                : themeAccentPalettes[accentName],
            setAccentName,
            toggleTheme,
        }),
        [accentName, setAccentName, themeName, toggleTheme],
    )

    return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export { useTheme } from "@/providers/theme-provider.context"
