import { StyleSheet } from "react-native"

import { colors } from "@/theme/colors"
import { spacing } from "@/theme/spacing"

export const favoritesScreenStyles = StyleSheet.create({
    screen: {
        flex: 1,
        backgroundColor: colors.background,
    },
    emptyContainer: {
        flex: 1,
        backgroundColor: colors.background,
    },
    emptyContent: {
        alignItems: "center",
        flex: 1,
        justifyContent: "center",
        paddingHorizontal: spacing.md,
    },
    listContent: {
        paddingTop: spacing.md,
        paddingBottom: spacing.xl,
    },
    stateContent: {
        gap: spacing.lg,
        paddingBottom: spacing.xl,
        paddingTop: spacing.md,
    },
    loaderWrap: {
        alignItems: "center",
        justifyContent: "center",
        minHeight: 140,
    },
    bookmarkButton: {
        alignItems: "center",
        borderRadius: 22,
        height: 44,
        justifyContent: "center",
        width: 44,
    },
    bookmarkButtonPressed: {
        opacity: 0.7,
    },
    bookmarkButtonDisabled: {
        opacity: 0.35,
    },
    swipeActionContainer: {
        paddingHorizontal: spacing.sm,
        paddingVertical: spacing.xs,
    },
    swipeAction: {
        flex: 1,
    },
    separator: {
        height: spacing.sm,
    },
})
