import { StyleSheet } from "react-native"

import { colors } from "@/theme/colors"
import { spacing } from "@/theme/spacing"

export const chatScreenStyles = StyleSheet.create({
    container: {
        backgroundColor: colors.surface,
        flex: 1,
    },
    content: {
        backgroundColor: colors.surface,
        flexGrow: 1,
        paddingBottom: spacing.md,
    },
    emptyWrap: {
        alignItems: "center",
        backgroundColor: colors.surface,
        flex: 1,
        justifyContent: "center",
        minHeight: 420,
        paddingHorizontal: spacing.md,
    },
    iconWrap: {
        alignItems: "center",
        backgroundColor: colors.surfaceElevated,
        borderRadius: 20,
        height: 56,
        justifyContent: "center",
        width: 56,
    },
})
