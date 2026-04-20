import { StyleSheet } from "react-native"

import { colors } from "@/theme/colors"
import { spacing } from "@/theme/spacing"

export const checkoutScreenStyles = StyleSheet.create({
    container: {
        backgroundColor: colors.background,
        flex: 1,
    },
    content: {
        gap: spacing.lg,
        padding: spacing.lg,
        paddingBottom: spacing.xxl,
    },
    heroCard: {
        backgroundColor: colors.surface,
        borderColor: "rgba(17,17,17,0.08)",
        borderRadius: 28,
        borderWidth: 1,
        gap: spacing.sm,
        padding: spacing.lg,
    },
    eyebrow: {
        color: colors.mutedText,
        fontSize: 12,
        fontWeight: "700",
        letterSpacing: 0.4,
        textTransform: "uppercase",
    },
    title: {
        color: colors.text,
        fontSize: 28,
        fontWeight: "800",
        lineHeight: 34,
    },
    subtitle: {
        color: colors.mutedText,
        fontSize: 15,
        lineHeight: 22,
    },
    summaryCard: {
        backgroundColor: colors.surface,
        borderColor: "rgba(17,17,17,0.08)",
        borderRadius: 24,
        borderWidth: 1,
        gap: spacing.md,
        padding: spacing.lg,
    },
    sectionTitle: {
        color: colors.text,
        fontSize: 18,
        fontWeight: "800",
        lineHeight: 22,
    },
    infoList: {
        gap: spacing.sm,
    },
    infoRow: {
        gap: 4,
    },
    infoLabel: {
        color: colors.mutedText,
        fontSize: 12,
        fontWeight: "700",
        letterSpacing: 0.35,
        textTransform: "uppercase",
    },
    infoValue: {
        color: colors.text,
        fontSize: 15,
        fontWeight: "600",
        lineHeight: 21,
    },
    actionRow: {
        flexDirection: "row",
        gap: spacing.sm,
    },
    secondaryButton: {
        alignItems: "center",
        borderColor: "rgba(17,17,17,0.12)",
        borderRadius: 16,
        borderWidth: 1,
        justifyContent: "center",
        minHeight: 48,
        paddingHorizontal: spacing.md,
    },
    secondaryButtonPressed: {
        opacity: 0.72,
    },
    secondaryButtonText: {
        color: colors.text,
        fontSize: 14,
        fontWeight: "700",
    },
})
