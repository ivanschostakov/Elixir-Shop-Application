import { StyleSheet } from "react-native"

export const WEB_BREAKPOINTS = {
    sm: 640,
    md: 960,
    lg: 1280,
} as const

export const emptyStateWebStyles = StyleSheet.create({
    fill: {
        height: "100%",
        width: "100%",
    },
    webEmptyState: {
        alignSelf: "center",
        maxWidth: 560,
        width: "100%",
    },
    webEmptyStateDesktop: {
        paddingHorizontal: 28,
        paddingVertical: 28,
    },
    webIllustration: {
        height: "100%",
        width: "100%",
    },
    webIllustrationWrap: {
        maxWidth: "100%",
    },
})
