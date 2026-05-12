import { useCallback, useEffect, useMemo, useState } from "react"
import * as SecureStore from "expo-secure-store"
import { Appearance, Platform } from "react-native"

import { ThemeContext } from "@/providers/theme-provider.context"
import type { ThemeProviderProps } from "@/providers/theme-provider.types"
import { themeAccentPalettes, type ThemeAccentName, type ThemeName } from "@/theme/colors"

const THEME_STORAGE_KEY = "elixirpeptide-theme"
const THEME_ACCENT_STORAGE_KEY = "elixirpeptide-theme-accent"

function isThemeName(value: string | null): value is ThemeName {
    return value === "light" || value === "dark"
}

function isThemeAccentName(value: string | null): value is ThemeAccentName {
    return value === "blue" || value === "teal" || value === "emerald" || value === "rose" || value === "amber"
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
        return isThemeAccentName(storedAccentName) ? storedAccentName : null
    }

    try {
        const storedAccentName = await SecureStore.getItemAsync(THEME_ACCENT_STORAGE_KEY)
        return isThemeAccentName(storedAccentName) ? storedAccentName : null
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
    Appearance.setColorScheme(themeName)
}

function getSystemThemeName(): ThemeName {
    return Appearance.getColorScheme() === "dark" ? "dark" : "light"
}

export function ThemeProvider({ children }: ThemeProviderProps) {
    const [themeName, setThemeName] = useState<ThemeName>(getSystemThemeName)
    const [accentName, setAccentNameState] = useState<ThemeAccentName>("blue")

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
            applyTheme(storedThemeName)
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
        setThemeName((currentThemeName) => {
            const nextThemeName = currentThemeName === "dark" ? "light" : "dark"
            applyTheme(nextThemeName)
            void persistTheme(nextThemeName)
            return nextThemeName
        })
    }, [])

    const setAccentName = useCallback((nextAccentName: ThemeAccentName) => {
        setAccentNameState(nextAccentName)
        void persistAccent(nextAccentName)
    }, [])

    const value = useMemo(
        () => ({
            isDark: themeName === "dark",
            themeName,
            accentName,
            accentPalette: themeAccentPalettes[accentName],
            setAccentName,
            toggleTheme,
        }),
        [accentName, setAccentName, themeName, toggleTheme],
    )

    return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export { useTheme } from "@/providers/theme-provider.context"
