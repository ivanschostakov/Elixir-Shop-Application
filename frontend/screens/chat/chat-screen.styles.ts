import { StyleSheet } from "react-native"

import { spacing } from "@/theme/spacing"

export const createChatScreenStyles = () => StyleSheet.create({
    keyboardContent: {
        flex: 1,
    },
    backgroundImage: {
        ...StyleSheet.absoluteFillObject,
    },
    backgroundImageHidden: {
        opacity: 0,
    },
    backgroundImageAsset: {
        opacity: 1,
    },
    backgroundScrim: {
        ...StyleSheet.absoluteFillObject,
    },
    backgroundScrimLight: {
        backgroundColor: "rgba(226,251,226,0.52)",
    },
    backgroundScrimDark: {
        backgroundColor: "rgba(15,21,29,0.42)",
    },
    dialogTopBlur: {
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        zIndex: 6,
    },
    inlineErrorWrap: {
        position: "absolute",
        left: spacing.md,
        right: spacing.md,
        zIndex: 13,
    },
    inlineError: {
        alignSelf: "center",
        borderRadius: 12,
        paddingHorizontal: spacing.sm,
        paddingVertical: spacing.xs,
        backgroundColor: "rgba(185,28,28,0.94)",
        color: "#FFF9F9",
        fontSize: 12,
        lineHeight: 16,
    },
    composerDock: {
        position: "absolute",
        left: spacing.sm,
        right: spacing.sm,
        bottom: 0,
        zIndex: 14,
        paddingTop: spacing.xs,
    },
    composerDockOverlay: {
        position: "absolute",
        left: 0,
        right: 0,
        paddingHorizontal: spacing.sm,
    }
})
