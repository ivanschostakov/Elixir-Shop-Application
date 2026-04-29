import { StyleSheet } from "react-native"

import { colors } from "@/theme/colors"
import { spacing } from "@/theme/spacing"

export const homeScreenStyles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: colors.pageBackground,
    },
    content: {
        gap: spacing.md,
        paddingBottom: 0,
        paddingHorizontal: 0,
        paddingTop: 0,
    },
    sectionBlock: {
        backgroundColor: colors.surface,
        borderRadius: spacing.lg,
        overflow: "hidden",
        paddingBottom: spacing.md,
        paddingTop: spacing.sm,
    },
    sectionBlockTop: {
        borderTopLeftRadius: 0,
        borderTopRightRadius: 0,
    },
    sectionBlockBottom: {
        borderBottomLeftRadius: 0,
        borderBottomRightRadius: 0,
    },
    loadingWrap: {
        alignItems: "center",
        justifyContent: "center",
        minHeight: 160,
    },
})
