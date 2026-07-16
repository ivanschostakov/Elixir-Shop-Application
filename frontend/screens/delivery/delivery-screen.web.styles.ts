import { StyleSheet } from "react-native"

import type { ThemePalette } from "@/theme/colors"

export const createDeliveryScreenWebStyles = (colors: ThemePalette) => StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: colors.pageBackground,
        position: "relative",
    },
    mapLayer: {
        flex: 1,
        position: "relative",
    },
    floatingControlsFrame: {
        alignItems: "center",
        paddingHorizontal: 12,
        paddingBottom: 12,
    },
    floatingControlsFrameTablet: {
        paddingHorizontal: 18,
        paddingBottom: 18,
    },
    floatingControlsFrameDesktop: {
        paddingHorizontal: 24,
        paddingBottom: 24,
    },
    floatingControlsStack: {
        width: "100%",
    },
    floatingControlsStackTablet: {
        maxWidth: 520,
    },
    floatingControlsStackDesktop: {
        maxWidth: 560,
    },
    floatingControlsRow: {
        alignItems: "stretch",
    },
    searchBlur: {
        ...StyleSheet.absoluteFillObject,
        backgroundColor: colors.veilSoft,
    },
    searchDismissOverlay: {
        ...StyleSheet.absoluteFillObject,
        zIndex: 5,
    },
    footerSurface: {
        alignSelf: "center",
        borderBottomLeftRadius: 28,
        borderBottomRightRadius: 28,
        overflow: "hidden",
        width: "100%",
    },
    footerContentTablet: {
        paddingHorizontal: 6,
    },
    footerContentDesktop: {
        paddingHorizontal: 8,
        paddingBottom: 8,
    },
})
