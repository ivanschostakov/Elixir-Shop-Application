import { Platform, StyleSheet } from "react-native"

import { colors } from "@/theme/colors"
import { spacing } from "@/theme/spacing"

export const stickyFooterStyles = StyleSheet.create({
    footerBase: {
        backgroundColor: colors.background,
        borderTopLeftRadius: spacing.xl,
        borderTopRightRadius: spacing.xl,
        ...Platform.select({
            web: {
                boxShadow: "0 -4px 16px rgba(0, 0, 0, 0.12)",
            },
            default: {
                shadowColor: "#000000",
                shadowOffset: { width: 0, height: -4 },
                shadowOpacity: 0.12,
                shadowRadius: 16,
            },
        }),
        paddingBottom: spacing.md,
    },
    elevatedSurface: {
        backgroundColor: colors.surface,
        borderTopLeftRadius: 24,
        borderTopRightRadius: 24,
        elevation: 16,
    },
    stack: {
        gap: 0,
    },
    actionKeyboardLayer: {
        width: "100%",
    },
    actionSection: {
        paddingHorizontal: spacing.md,
        paddingTop: spacing.sm,
        paddingBottom: 0,
    },
    searchSection: {
        paddingHorizontal: spacing.md,
        paddingTop: spacing.sm,
        paddingBottom: 0,
    },
    navRow: {
        alignItems: "stretch",
        flexDirection: "row",
        paddingHorizontal: spacing.xs,
        paddingTop: spacing.xs,
        paddingBottom: 0,
    },
    footerItem: {
        flex: 1,
    },
    iconButton: {
        alignItems: "center",
        borderRadius: 18,
        justifyContent: "center",
        minHeight: 48,
        paddingHorizontal: 4,
        paddingVertical: spacing.xs,
    },
    iconButtonPressed: {
        opacity: 0.7,
    },
    iconLabel: {
        color: colors.mutedText,
        fontSize: 11,
        fontWeight: "700",
    },
    iconLabelActive: {
        color: colors.primary,
    },
    iconWrap: {
        position: "relative",
    },
    basketBadge: {
        backgroundColor: "#ef4444",
        borderColor: colors.background,
        borderRadius: 5,
        borderWidth: 1.5,
        height: 10,
        position: "absolute",
        right: -4,
        top: -2,
        width: 10,
    },
    actionButton: {
        alignItems: "center",
        backgroundColor: colors.primary,
        borderRadius: 16,
        justifyContent: "center",
        minHeight: 56,
        paddingHorizontal: spacing.md,
        width: "100%",
    },
    actionButtonPressed: {
        backgroundColor: "#096FE0",
    },
    actionButtonDisabled: {
        opacity: 0.5,
    },
    actionButtonText: {
        color: "#FFFFFF",
        fontSize: 18,
        fontWeight: "800",
    },
    quantityControl: {
        alignItems: "center",
        backgroundColor: colors.primary,
        borderRadius: 16,
        flexDirection: "row",
        minHeight: 56,
        width: "100%",
    },
    quantityButton: {
        alignItems: "center",
        justifyContent: "center",
        minHeight: 56,
        width: 56,
    },
    quantityButtonPressed: {
        backgroundColor: "rgba(255, 255, 255, 0.14)",
    },
    quantityButtonDisabled: {
        opacity: 0.45,
    },
    quantityButtonText: {
        color: "#FFFFFF",
        fontSize: 28,
        fontWeight: "700",
        lineHeight: 30,
    },
    quantityValueWrap: {
        alignItems: "center",
        flex: 1,
        justifyContent: "center",
        minHeight: 56,
        paddingHorizontal: spacing.sm,
    },
    quantityValue: {
        color: "#FFFFFF",
        fontSize: 18,
        fontWeight: "800",
    },
})
