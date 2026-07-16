import { StyleSheet } from "react-native"

import type { ThemePalette } from "@/theme/colors"
import { spacing } from "@/theme/spacing"

export const createLegalContentStyles = (colors: ThemePalette) => StyleSheet.create({
    screen: {
        flex: 1,
        backgroundColor: colors.surface,
    },
    content: {
        backgroundColor: colors.pageBackground,
        paddingBottom: spacing.lg,
    },
    documentWrap: {
        backgroundColor: colors.surface,
        borderBottomLeftRadius: 24,
        borderBottomRightRadius: 24,
        marginBottom: spacing.md,
        paddingHorizontal: spacing.md,
        paddingTop: spacing.md,
        paddingBottom: spacing.md,
    },
    block: {
        gap: spacing.xs,
    },
    h1: {
        color: colors.text,
        fontSize: 24,
        fontWeight: "800",
        marginBottom: spacing.xs,
    },
    h2: {
        color: colors.text,
        fontSize: 18,
        fontWeight: "700",
        marginTop: spacing.md,
    },
    h3: {
        color: colors.text,
        fontSize: 14,
        fontWeight: "700",
        marginTop: spacing.sm,
    },
    body: {
        color: colors.stateText,
        fontSize: 15,
        lineHeight: 24,
    },
    bodyLink: {
        color: colors.primary,
        fontSize: 15,
        lineHeight: 24,
        fontWeight: "600",
    },
    spacer: {
        height: spacing.sm,
    },
    statusRow: {
        marginTop: spacing.md,
        gap: spacing.sm,
    },
    linkButton: {
        color: colors.primary,
        fontSize: 15,
        fontWeight: "700",
    },
})
