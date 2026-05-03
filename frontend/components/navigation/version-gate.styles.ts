import { StyleSheet } from "react-native"

export const versionGateStyles = StyleSheet.create({
    screen: {
        flex: 1,
        alignItems: "center",
        justifyContent: "center",
        paddingHorizontal: 24,
    },
    card: {
        width: "100%",
        maxWidth: 420,
        borderRadius: 8,
        borderWidth: 1,
        paddingHorizontal: 24,
        paddingVertical: 28,
    },
    eyebrow: {
        fontSize: 12,
        fontWeight: "700",
        letterSpacing: 0.4,
        marginBottom: 10,
        textTransform: "uppercase",
    },
    title: {
        fontSize: 26,
        fontWeight: "800",
        lineHeight: 32,
        marginBottom: 12,
    },
    text: {
        fontSize: 16,
        lineHeight: 23,
        marginBottom: 20,
    },
    button: {
        minHeight: 48,
        alignItems: "center",
        justifyContent: "center",
        borderRadius: 8,
        paddingHorizontal: 18,
    },
    buttonPressed: {
        opacity: 0.86,
    },
    buttonDisabled: {
        opacity: 0.58,
    },
    buttonText: {
        color: "#FFFFFF",
        fontSize: 16,
        fontWeight: "800",
    },
    helperText: {
        fontSize: 13,
        lineHeight: 18,
        marginTop: 12,
    },
    loadingScreen: {
        flex: 1,
        alignItems: "center",
        justifyContent: "center",
    },
})
