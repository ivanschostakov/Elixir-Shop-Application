import { StyleSheet } from "react-native"

export const rootLayoutStyles = StyleSheet.create({
    root: {
        flex: 1,
    },
    rootDark: {
        backgroundColor: "#070A0F",
    },
    rootLight: {
        backgroundColor: "#FFFFFF",
    },
    webDisabledScreen: {
        flex: 1,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "#f8fafc",
        paddingHorizontal: 24,
    },
    webDisabledCard: {
        width: "100%",
        maxWidth: 520,
        borderRadius: 28,
        paddingHorizontal: 28,
        paddingVertical: 32,
        backgroundColor: "#ffffff",
        borderWidth: 1,
        borderColor: "rgba(17, 24, 39, 0.08)",
    },
    webDisabledEyebrow: {
        color: "#6b7280",
        fontSize: 12,
        fontWeight: "700",
        letterSpacing: 0.4,
        textTransform: "uppercase",
        marginBottom: 10,
    },
    webDisabledTitle: {
        color: "#111827",
        fontSize: 28,
        fontWeight: "800",
        lineHeight: 34,
        marginBottom: 12,
    },
    webDisabledText: {
        color: "#4b5563",
        fontSize: 16,
        lineHeight: 24,
    },
})
