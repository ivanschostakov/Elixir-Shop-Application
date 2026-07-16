import type { PropsWithChildren } from "react"

import type {
    ThemeAccentName,
    ThemeAccentPalette,
    ThemeName,
    ThemePalette,
} from "@/theme/colors"

export type ThemeProviderProps = PropsWithChildren

export type ThemeContextValue = {
    isDark: boolean
    palette: ThemePalette
    themeName: ThemeName
    accentName: ThemeAccentName
    accentPalette: ThemeAccentPalette
    setAccentName: (accentName: ThemeAccentName) => void
    toggleTheme: () => void
}
