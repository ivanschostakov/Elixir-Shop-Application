import { createContext, useContext } from "react"

import type { ThemeContextValue } from "@/providers/theme-provider.types"

export const ThemeContext = createContext<ThemeContextValue>({
    isDark: false,
    themeName: "light",
    toggleTheme: () => undefined,
})

export function useTheme() {
    return useContext(ThemeContext)
}
