import { StyleSheet } from "react-native"

import { colors } from "@/theme/colors"

export const screenTemplateStyles = StyleSheet.create({
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
