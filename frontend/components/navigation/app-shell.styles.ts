import { StyleSheet } from "react-native"

import { colors } from "@/theme/colors"

export const appShellStyles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: colors.background,
        minHeight: "100%",
    },
    content: {
        flex: 1,
        minHeight: 0,
        backgroundColor: colors.background,
    },
})
