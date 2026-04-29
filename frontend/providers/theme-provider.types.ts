import type { PropsWithChildren } from "react"

import type { ThemeName } from "@/theme/colors"

export type ThemeProviderProps = PropsWithChildren

export type ThemeContextValue = {
    isDark: boolean
    themeName: ThemeName
    toggleTheme: () => void
}
