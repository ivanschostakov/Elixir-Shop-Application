import { createContext, useContext } from "react"

import { lightColors, themeAccentPalettes } from "@/theme/colors"
import type { ThemeContextValue } from "@/providers/theme-provider.types"

export const ThemeContext = createContext<ThemeContextValue>({
    isDark: false,
    palette: lightColors,
    themeName: "light",
    accentName: "vividBlue",
    accentPalette: themeAccentPalettes.vividBlue,
    setAccentName: () => undefined,
    toggleTheme: () => undefined,
})

export function useTheme() {
    return useContext(ThemeContext)
}
