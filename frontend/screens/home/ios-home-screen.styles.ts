import { StyleSheet } from "react-native"

import type { ThemePalette } from "@/theme/colors"
import { spacing } from "@/theme/spacing"

export const createIosHomeScreenStyles = (colors: ThemePalette) => StyleSheet.create({
    screen: {
        backgroundColor: colors.pageBackground,
        flex: 1,
    },
    content: {
        gap: spacing.md,
        paddingBottom: spacing.xl,
        paddingHorizontal: spacing.md,
    },
    hero: {
        backgroundColor: colors.primary,
        borderRadius: 28,
        overflow: "hidden",
        padding: spacing.lg,
    },
    heroGlow: {
        backgroundColor: "rgba(255,255,255,0.14)",
        borderRadius: 120,
        height: 180,
        position: "absolute",
        right: -48,
        top: -72,
        width: 180,
    },
    heroToolbar: {
        alignItems: "center",
        flexDirection: "row",
        justifyContent: "space-between",
        marginBottom: spacing.lg,
    },
    logo: {
        height: 46,
        width: 46,
    },
    languageSwitcher: {
        backgroundColor: "rgba(0,0,0,0.14)",
        borderRadius: 14,
        flexDirection: "row",
        gap: 2,
        padding: 3,
    },
    languageOption: {
        alignItems: "center",
        borderRadius: 11,
        justifyContent: "center",
        minHeight: 30,
        minWidth: 34,
        paddingHorizontal: 7,
    },
    languageOptionSelected: {
        backgroundColor: "#FFFFFF",
    },
    languageOptionText: {
        color: "rgba(255,255,255,0.72)",
        fontSize: 12,
        fontWeight: "800",
    },
    languageOptionTextSelected: {
        color: colors.primary,
    },
    eyebrow: {
        color: "rgba(255,255,255,0.78)",
        fontSize: 13,
        fontWeight: "800",
        letterSpacing: 0.8,
        textTransform: "uppercase",
    },
    title: {
        color: "#FFFFFF",
        fontSize: 30,
        fontWeight: "900",
        letterSpacing: -0.7,
        lineHeight: 35,
        marginTop: spacing.sm,
        maxWidth: 520,
    },
    body: {
        color: "rgba(255,255,255,0.86)",
        fontSize: 16,
        lineHeight: 23,
        marginTop: spacing.sm,
        maxWidth: 560,
    },
    sectionTitle: {
        color: colors.text,
        fontSize: 20,
        fontWeight: "800",
        marginTop: spacing.sm,
    },
    actionGrid: {
        flexDirection: "row",
        flexWrap: "wrap",
        gap: spacing.sm,
    },
    actionCard: {
        backgroundColor: colors.surface,
        borderColor: colors.border,
        borderRadius: 20,
        borderWidth: StyleSheet.hairlineWidth,
        flexBasis: "47%",
        flexGrow: 1,
        minHeight: 150,
        padding: spacing.md,
    },
    actionCardPressed: {
        opacity: 0.88,
        transform: [{ scale: 0.99 }],
    },
    actionIcon: {
        fontSize: 27,
        marginBottom: spacing.lg,
    },
    actionTitle: {
        color: colors.text,
        fontSize: 16,
        fontWeight: "800",
    },
    actionBody: {
        color: colors.stateText,
        fontSize: 13,
        lineHeight: 18,
        marginTop: spacing.xs,
    },
    notice: {
        backgroundColor: colors.surface,
        borderColor: colors.border,
        borderRadius: 20,
        borderWidth: StyleSheet.hairlineWidth,
        padding: spacing.md,
    },
    noticeLabel: {
        color: colors.primary,
        fontSize: 13,
        fontWeight: "800",
        textTransform: "uppercase",
    },
    noticeTitle: {
        color: colors.text,
        fontSize: 18,
        fontWeight: "800",
        marginTop: spacing.sm,
    },
    noticeBody: {
        color: colors.stateText,
        fontSize: 14,
        lineHeight: 21,
        marginTop: spacing.xs,
    },
})
