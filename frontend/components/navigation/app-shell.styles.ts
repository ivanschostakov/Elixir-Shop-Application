import { StyleSheet } from "react-native"

import type { ThemePalette } from "@/theme/colors"

export const createAppShellStyles = (colors: ThemePalette) => StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: colors.background,
        minHeight: "100%",
    },
    safeArea: {
        flex: 1,
    },
    discoverTopGradient: {
        left: 0,
        position: "absolute",
        right: 0,
        top: 0,
        zIndex: 1,
    },
    brandLabelOverlay: {
        alignItems: "center",
        left: 0,
        position: "absolute",
        right: 0,
        zIndex: 40,
    },
    brandLabelPill: {
        alignItems: "center",
        backgroundColor: colors.primary,
        borderRadius: 17,
        flexDirection: "row",
        gap: 4,
        height: 32,
        justifyContent: "center",
        overflow: "hidden",
        paddingHorizontal: 7,
        width: 124,
    },
    brandLabelImage: {
        height: 24,
        width: 26,
    },
    brandLabelText: {
        color: colors.onPrimary,
        flexShrink: 1,
        fontSize: 11,
        fontWeight: "700",
        letterSpacing: 0.1,
    },
    content: {
        flex: 1,
        minHeight: 0,
        backgroundColor: colors.background,
        zIndex: 2,
    },
})
