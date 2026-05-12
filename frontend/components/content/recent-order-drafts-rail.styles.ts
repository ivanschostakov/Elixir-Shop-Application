import { StyleSheet } from "react-native"

import { colors } from "@/theme/colors"
import { spacing } from "@/theme/spacing"

const DRAFTS_RAIL_MIN_HEIGHT = 548

export const recentOrderDraftsRailStyles = StyleSheet.create({
    section: {
        backgroundColor: colors.surface,
        borderTopColor: colors.divider,
        borderTopWidth: 1,
        gap: spacing.sm,
        minHeight: DRAFTS_RAIL_MIN_HEIGHT,
        overflow: "hidden",
        paddingBottom: spacing.md,
        paddingTop: spacing.md,
    },
    scrollView: {
        flexGrow: 0,
    },
    scrollContent: {
        gap: spacing.md,
        paddingHorizontal: spacing.md,
    },
    card: {
        backgroundColor: colors.surface,
        borderRadius: 30,
        gap: spacing.md,
        overflow: "hidden",
        padding: 12,
        position: "relative",
        width: 224,
    },
    cardPressed: {
        opacity: 0.94,
        transform: [{ scale: 0.985 }],
    },
    collage: {
        aspectRatio: 1,
        backgroundColor: colors.surfaceMuted,
        borderRadius: 24,
        overflow: "hidden",
    },
    collageTile: {
        backgroundColor: colors.railTile,
        overflow: "hidden",
        position: "absolute",
    },
    collageTileImage: {
        height: "100%",
        width: "100%",
    },
    cardBody: {
        flex: 1,
        gap: spacing.xs,
    },
    cardTitleButton: {
        alignSelf: "flex-start",
        borderBottomColor: colors.text,
        borderBottomWidth: 1,
        maxWidth: "100%",
        paddingBottom: 2,
    },
    cardTitleButtonPressed: {
        opacity: 0.72,
    },
    cardTitleButtonDisabled: {
        opacity: 0.72,
    },
    cardTitle: {
        color: colors.text,
        fontSize: 18,
        fontWeight: "800",
        lineHeight: 22,
    },
    cardTitleInput: {
        borderBottomColor: colors.text,
        borderBottomWidth: 1,
        color: colors.text,
        fontSize: 18,
        fontWeight: "800",
        lineHeight: 22,
        minHeight: 30,
        paddingBottom: 2,
        paddingHorizontal: 0,
        paddingTop: 0,
    },
    cardTitleInputSaving: {
        opacity: 0.72,
    },
    cardSubtitle: {
        color: colors.mutedText,
        fontSize: 13,
        lineHeight: 18,
        minHeight: 72,
    },
    cardFooter: {
        alignItems: "flex-start",
        flexDirection: "row",
        gap: spacing.sm,
        marginTop: "auto",
    },
    cardCtaButton: {
        alignSelf: "stretch",
        alignItems: "center",
        backgroundColor: colors.primary,
        borderBottomLeftRadius: 16,
        borderBottomRightRadius: 16,
        borderTopLeftRadius: 0,
        borderTopRightRadius: 0,
        justifyContent: "center",
        marginTop: spacing.sm,
        minHeight: 44,
        paddingHorizontal: spacing.md,
    },
    cardCtaButtonPressed: {
        opacity: 0.88,
    },
    cardCtaButtonDisabled: {
        opacity: 0.68,
    },
    cardCtaButtonText: {
        color: colors.onPrimary,
        fontSize: 16,
        fontWeight: "900",
    },
    cardPositions: {
        color: colors.mutedText,
        flex: 1,
        fontSize: 13,
        fontWeight: "700",
    },
    cardDeleteBadge: {
        alignItems: "center",
        backgroundColor: "#FDECEF",
        borderRadius: 999,
        borderWidth: 0,
        height: 26,
        justifyContent: "center",
        position: "absolute",
        right: 12,
        top: 12,
        width: 26,
        zIndex: 2,
    },
    cardDeleteBadgePressed: {
        opacity: 0.72,
    },
    cardDeleteBadgeDisabled: {
        opacity: 0.45,
    },
})
