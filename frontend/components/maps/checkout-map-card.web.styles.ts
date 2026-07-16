import type { ThemePalette } from "@/theme/colors"

export const createCheckoutMapCardWebStyles = (colors: ThemePalette) => ({
    container: {
        flex: 1,
        backgroundColor: colors.background,
    },
    mapFallback: {
        alignItems: "center" as const,
        backgroundColor: "#edf3fb",
        flex: 1,
        gap: 8,
        justifyContent: "center" as const,
        paddingHorizontal: 24,
    },
    mapFallbackTitle: {
        color: colors.text,
        fontSize: 18,
        fontWeight: "800" as const,
    },
    mapFallbackText: {
        color: colors.mutedText,
        fontSize: 14,
        lineHeight: 21,
        textAlign: "center" as const,
    },
})
