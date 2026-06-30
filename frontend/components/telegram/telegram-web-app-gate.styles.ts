import { StyleSheet } from "react-native"

import { colors } from "@/theme/colors"

export const telegramWebAppGateStyles = StyleSheet.create({
    screen: {
        flex: 1,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: colors.pageBackground,
        paddingHorizontal: 20,
    },
    panel: {
        width: "100%",
        maxWidth: 460,
        borderRadius: 8,
        borderWidth: 1,
        borderColor: colors.border,
        backgroundColor: colors.surface,
        paddingHorizontal: 24,
        paddingVertical: 26,
    },
    eyebrow: {
        color: colors.stateText,
        fontSize: 12,
        fontWeight: "700",
        letterSpacing: 0,
        marginBottom: 8,
        textTransform: "uppercase",
    },
    title: {
        color: colors.text,
        fontSize: 24,
        fontWeight: "800",
        lineHeight: 30,
        marginBottom: 10,
    },
    text: {
        color: colors.mutedText,
        fontSize: 15,
        lineHeight: 22,
        marginBottom: 18,
    },
    errorText: {
        color: colors.danger,
        fontSize: 14,
        lineHeight: 20,
        marginBottom: 14,
    },
    button: {
        minHeight: 48,
        alignItems: "center",
        justifyContent: "center",
        borderRadius: 8,
        backgroundColor: colors.primary,
        paddingHorizontal: 18,
    },
    buttonPressed: {
        opacity: 0.86,
    },
    buttonDisabled: {
        opacity: 0.58,
    },
    buttonText: {
        color: colors.onPrimary,
        fontSize: 15,
        fontWeight: "800",
        lineHeight: 20,
    },
    loadingRow: {
        flexDirection: "row",
        alignItems: "center",
        gap: 10,
    },
    loadingText: {
        color: colors.mutedText,
        fontSize: 15,
        lineHeight: 22,
    },
})
