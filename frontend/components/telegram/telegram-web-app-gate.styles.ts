import { StyleSheet } from "react-native"

export const telegramWebAppGateStyles = StyleSheet.create({
    screen: {
        flex: 1,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "#f6f8fb",
        paddingHorizontal: 20,
    },
    panel: {
        width: "100%",
        maxWidth: 460,
        borderRadius: 8,
        borderWidth: 1,
        borderColor: "rgba(15, 23, 42, 0.1)",
        backgroundColor: "#ffffff",
        paddingHorizontal: 24,
        paddingVertical: 26,
    },
    eyebrow: {
        color: "#52708f",
        fontSize: 12,
        fontWeight: "700",
        letterSpacing: 0,
        marginBottom: 8,
        textTransform: "uppercase",
    },
    title: {
        color: "#172033",
        fontSize: 24,
        fontWeight: "800",
        lineHeight: 30,
        marginBottom: 10,
    },
    text: {
        color: "#526071",
        fontSize: 15,
        lineHeight: 22,
        marginBottom: 18,
    },
    errorText: {
        color: "#b42318",
        fontSize: 14,
        lineHeight: 20,
        marginBottom: 14,
    },
    button: {
        minHeight: 48,
        alignItems: "center",
        justifyContent: "center",
        borderRadius: 8,
        backgroundColor: "#2d6aa3",
        paddingHorizontal: 18,
    },
    buttonPressed: {
        opacity: 0.86,
    },
    buttonDisabled: {
        opacity: 0.58,
    },
    buttonText: {
        color: "#ffffff",
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
        color: "#526071",
        fontSize: 15,
        lineHeight: 22,
    },
})
