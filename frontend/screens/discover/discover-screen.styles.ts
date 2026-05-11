import { StyleSheet } from "react-native"

import { colors } from "@/theme/colors"
import { spacing } from "@/theme/spacing"

export const discoverScreenStyles = StyleSheet.create({
    screen: {
        flex: 1,
        backgroundColor: colors.surface,
    },
    articleEmptyScreen: {
        flex: 1,
        backgroundColor: colors.background,
    },
    emptyContent: {
        alignItems: "center",
        flex: 1,
        justifyContent: "center",
        paddingHorizontal: spacing.md,
    },
    list: {
        flex: 1,
        backgroundColor: colors.surface,
        width: "100%",
    },
    listContent: {
        backgroundColor: colors.pageBackground,
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
    gridRow: {
        backgroundColor: colors.surface,
        borderRadius: 28,
        flexDirection: "row",
        overflow: "hidden",
        paddingHorizontal: 0,
    },
    gridItem: {
        width: "100%",
    },
    gridItemColumn: {
        flex: 1,
        minWidth: 0,
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
