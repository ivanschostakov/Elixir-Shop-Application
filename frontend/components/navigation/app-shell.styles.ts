import { StyleSheet } from "react-native"

import { colors } from "@/theme/colors"

export const appShellStyles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: colors.background,
        minHeight: "100%",
    },
    safeArea: {
        flex: 1,
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
    },
})
