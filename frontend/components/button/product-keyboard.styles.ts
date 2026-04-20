import { StyleSheet } from "react-native"

import { colors } from "@/theme/colors"
import { spacing } from "@/theme/spacing"

export const productKeyboardStyles = StyleSheet.create({
    container: {
        position: "absolute",
        left: 0,
        right: 0,
        bottom: 0,
        flexDirection: "row",
        alignItems: "center",
        gap: spacing.sm,
        paddingTop: spacing.sm,
        paddingHorizontal: spacing.md,
        paddingBottom: spacing.md,
    },
    buyButton: {
        flex: 1,
        minHeight: 48,
        borderRadius: 12,
        alignItems: "center",
        justifyContent: "center",
        paddingHorizontal: spacing.md,
        backgroundColor: colors.primary,
    },
    cartButton: {
        flex: 1,
        minHeight: 48,
        borderRadius: 12,
        alignItems: "center",
        justifyContent: "center",
        paddingHorizontal: spacing.md,
        backgroundColor: colors.surface,
        borderWidth: 1,
        borderColor: colors.border,
    },
    buyButtonText: {
        fontSize: 16,
        fontWeight: "700",
        color: "#ffffff",
    },
    cartButtonText: {
        fontSize: 16,
        fontWeight: "600",
        color: colors.text,
    },
})
