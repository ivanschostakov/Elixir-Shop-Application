import { StyleSheet } from "react-native"

import { colors } from "@/theme/colors"
import { spacing } from "@/theme/spacing"

export const discoverScreenStyles = StyleSheet.create({
    screen: {
        flex: 1,
        backgroundColor: "#F3F5F8",
    },
    list: {
        flex: 1,
        backgroundColor: "#F3F5F8",
        width: "100%",
    },
    listContent: {
        paddingBottom: spacing.lg,
        paddingTop: 0,
    },
    controlsWrap: {
        backgroundColor: colors.surface,
        borderBottomLeftRadius: 24,
        borderBottomRightRadius: 24,
        marginBottom: spacing.md,
        paddingHorizontal: spacing.sm,
        paddingVertical: spacing.md,
        width: "100%",
    },
    introBlock: {
        height: spacing.xs,
    },
    gridRow: {
        backgroundColor: colors.surface,
        borderRadius: 28,
        justifyContent: "space-between",
        overflow: "hidden",
        paddingHorizontal: 0,
    },
    gridItem: {
        flex: 1,
    },
    gridItemCard: {
        borderRadius: 0,
        overflow: "visible",
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
