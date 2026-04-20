import { StyleSheet } from "react-native"

import { colors } from "@/theme/colors"
import { spacing } from "@/theme/spacing"

export const homeScreenStyles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: colors.background,
    },
    content: {
        gap: spacing.xl,
        paddingBottom: spacing.xl,
        paddingTop: spacing.md,
    },
    loadingWrap: {
        alignItems: "center",
        justifyContent: "center",
        minHeight: 120,
    },
})
