import { StyleSheet } from "react-native"
import type { ThemePalette } from "@/theme/colors"
import { spacing } from "@/theme/spacing"
import { IMAGE_CAROUSEL_CARD_GAP } from "./image-carousel.constants"

export const createImageCarouselStyles = (colors: ThemePalette) => StyleSheet.create({
    scrollView: {
        alignSelf: "center",
        backgroundColor: colors.background,
    },
    container: {
        gap: IMAGE_CAROUSEL_CARD_GAP,
        backgroundColor: colors.background,
    },
    item: {
        flexShrink: 0,
    },
    image: {
        width: "100%",
        aspectRatio: 1,
        borderRadius: 16,
        backgroundColor: colors.background,
        marginBottom: spacing.sm,
    },
    title: {
        color: colors.text,
        fontSize: 14,
        fontWeight: "600",
    },
})
