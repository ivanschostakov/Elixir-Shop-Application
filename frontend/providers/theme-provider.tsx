import { useCallback, useEffect, useMemo, useState } from "react"
import * as SecureStore from "expo-secure-store"
import { Appearance, Platform } from "react-native"

import { ThemeContext } from "@/providers/theme-provider.context"
import type { ThemeProviderProps } from "@/providers/theme-provider.types"
import type { ThemeName } from "@/theme/colors"

const THEME_STORAGE_KEY = "elixirshop-theme"

function isThemeName(value: string | null): value is ThemeName {
    return value === "light" || value === "dark"
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

function applyTheme(themeName: ThemeName) {
    Appearance.setColorScheme(themeName)
}

function getSystemThemeName(): ThemeName {
    return Appearance.getColorScheme() === "dark" ? "dark" : "light"
}

export function ThemeProvider({ children }: ThemeProviderProps) {
    const [themeName, setThemeName] = useState<ThemeName>(getSystemThemeName)

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

    const toggleTheme = useCallback(() => {
        setThemeName((currentThemeName) => {
            const nextThemeName = currentThemeName === "dark" ? "light" : "dark"
            applyTheme(nextThemeName)
            void persistTheme(nextThemeName)
            return nextThemeName
        })
    }, [])

    const value = useMemo(
        () => ({
            isDark: themeName === "dark",
            themeName,
            toggleTheme,
        }),
        [themeName, toggleTheme],
    )

    return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export { useTheme } from "@/providers/theme-provider.context"
