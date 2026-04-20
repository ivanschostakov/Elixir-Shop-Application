import { StyleSheet } from "react-native";

export const debugGridStyles = StyleSheet.create({
    overlay: {
        ...StyleSheet.absoluteFillObject,
    },
    vLine: {
        position: "absolute",
        top: 0,
        bottom: 0,
        width: 1,
        backgroundColor: "rgba(0,0,255,0.15)",
    },
    hLine: {
        position: "absolute",
        left: 0,
        right: 0,
        height: 1,
        backgroundColor: "rgba(0,0,255,0.15)",
    },
    centerLine: {
        backgroundColor: "rgba(255,0,0,0.4)",
    },
});