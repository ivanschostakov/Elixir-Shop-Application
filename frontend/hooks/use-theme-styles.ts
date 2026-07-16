import { useMemo } from "react"

import { useTheme } from "@/providers/theme-provider"
import type { ThemePalette } from "@/theme/colors"

const styleCache = new WeakMap<
    (palette: ThemePalette) => unknown,
    WeakMap<ThemePalette, unknown>
>()

function getThemeStyles<TStyles>(createStyles: (palette: ThemePalette) => TStyles, palette: ThemePalette) {
    let paletteCache = styleCache.get(createStyles)
    if (!paletteCache) {
        paletteCache = new WeakMap<ThemePalette, unknown>()
        styleCache.set(createStyles, paletteCache)
    }

    const cachedStyles = paletteCache.get(palette) as TStyles | undefined
    if (cachedStyles) {
        return cachedStyles
    }

    const styles = createStyles(palette)
    paletteCache.set(palette, styles)
    return styles
}

export function useThemeStyles<TStyles>(createStyles: (palette: ThemePalette) => TStyles): TStyles {
    const { palette } = useTheme()

    return useMemo(() => getThemeStyles(createStyles, palette), [createStyles, palette])
}
