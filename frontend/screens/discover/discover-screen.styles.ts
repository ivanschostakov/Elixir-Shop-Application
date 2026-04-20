import { StyleSheet } from "react-native"

import { colors } from "@/theme/colors"
import { spacing } from "@/theme/spacing"

export const discoverScreenStyles = StyleSheet.create({
    screen: {
        flex: 1,
        backgroundColor: colors.background,
    },
    list: {
        flex: 1,
        width: "100%",
    },
    listContent: {
        gap: spacing.md,
        paddingBottom: spacing.lg,
        paddingTop: spacing.sm,
    },
    controlsWrap: {
        marginBottom: 2,
        paddingHorizontal: spacing.md,
        width: "100%",
    },
    introBlock: {
        height: spacing.xs,
    },
    gridRow: {
        gap: spacing.md,
        justifyContent: "space-between",
        paddingHorizontal: spacing.md,
    },
    gridItem: {
        flex: 1,
    },
    loaderWrap: {
        alignItems: "center",
        justifyContent: "center",
        minHeight: 180,
    },
    footerLoaderWrap: {
        alignItems: "center",
        justifyContent: "center",
        paddingBottom: spacing.md,
        paddingTop: spacing.xs,
    },
})
