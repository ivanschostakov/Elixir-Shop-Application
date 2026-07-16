import { StyleSheet } from "react-native"

import type { ThemePalette } from "@/theme/colors"

export const createScreenTemplateStyles = (colors: ThemePalette) => StyleSheet.create({
    chromeOverlay: {
        ...StyleSheet.absoluteFillObject,
    },
    fullscreen: {
        flex: 1,
        backgroundColor: colors.background,
    },
    screen: {
        flex: 1,
        backgroundColor: colors.background,
    },
    scroll: {
        flex: 1,
    },
})
