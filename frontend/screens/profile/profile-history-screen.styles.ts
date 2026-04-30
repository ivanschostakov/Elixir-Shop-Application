import { StyleSheet } from "react-native"

import { colors } from "@/theme/colors"
import { spacing } from "@/theme/spacing"

export const profileHistoryScreenStyles = StyleSheet.create({
    screen: {
        flex: 1,
        backgroundColor: colors.surface,
    },
    headerTabsSlot: {
        minWidth: 220,
    },
    list: {
        backgroundColor: colors.surface,
        flex: 1,
        width: "100%",
    },
    listContent: {
        backgroundColor: colors.pageBackground,
        paddingBottom: spacing.lg,
        paddingTop: 0,
    },
    listContentEmpty: {
        flexGrow: 1,
    },
    controlsWrap: {
        backgroundColor: colors.surface,
        borderBottomLeftRadius: 24,
        borderBottomRightRadius: 24,
        marginBottom: spacing.sm,
        paddingHorizontal: spacing.sm,
        paddingVertical: spacing.md,
        width: "100%",
    },
    cardWrap: {
        backgroundColor: colors.surface,
        borderRadius: 28,
        marginBottom: spacing.md,
        paddingHorizontal: spacing.sm,
        width: "100%",
    },
    historyCard: {
        backgroundColor: colors.surface,
        borderRadius: 28,
        gap: spacing.md,
        overflow: "hidden",
        padding: 12,
    },
    historyCardPressed: {
        opacity: 0.86,
        transform: [{ scale: 0.99 }],
    },
    historyCardCollage: {
        aspectRatio: 1,
        backgroundColor: colors.surfaceMuted,
        borderRadius: 24,
        overflow: "hidden",
    },
    historyCardCollageTile: {
        backgroundColor: colors.railTile,
        overflow: "hidden",
        position: "absolute",
    },
    historyCardCollageTileImage: {
        height: "100%",
        width: "100%",
    },
    historyCardHeader: {
        alignItems: "flex-start",
        flexDirection: "row",
        gap: spacing.md,
        justifyContent: "space-between",
    },
    historyCardCopy: {
        flex: 1,
        gap: spacing.xs,
        minWidth: 0,
    },
    historyCardEyebrow: {
        color: colors.primary,
        fontSize: 11,
        fontWeight: "700",
        letterSpacing: 0.8,
        textTransform: "uppercase",
    },
    historyCardTitle: {
        color: colors.text,
        fontSize: 20,
        fontWeight: "800",
    },
    historyCardSubtitle: {
        color: colors.mutedText,
        fontSize: 14,
        lineHeight: 22,
    },
    historyCardBadge: {
        borderRadius: 999,
        paddingHorizontal: spacing.md,
        paddingVertical: spacing.sm,
    },
    historyCardBadgeActive: {
        backgroundColor: colors.primaryMuted,
    },
    historyCardBadgeCompleted: {
        backgroundColor: colors.successMuted,
    },
    historyCardBadgeText: {
        fontSize: 12,
        fontWeight: "800",
        letterSpacing: 0.4,
        textTransform: "uppercase",
    },
    historyCardBadgeTextActive: {
        color: colors.primary,
    },
    historyCardBadgeTextCompleted: {
        color: colors.success,
    },
    historyCardMetaGrid: {
        gap: spacing.sm,
    },
    historyCardMetaRow: {
        alignItems: "center",
        flexDirection: "row",
        gap: spacing.md,
        justifyContent: "space-between",
    },
    historyCardMetaLabel: {
        color: colors.mutedText,
        fontSize: 13,
        fontWeight: "700",
    },
    historyCardMetaValue: {
        color: colors.text,
        flexShrink: 1,
        fontSize: 15,
        fontWeight: "700",
        textAlign: "right",
    },
    historyCardDivider: {
        height: 1,
        backgroundColor: colors.border,
    },
    historyCardFooter: {
        alignItems: "center",
        flexDirection: "row",
        justifyContent: "space-between",
    },
    historyCardFooterLabel: {
        color: colors.mutedText,
        fontSize: 13,
        fontWeight: "700",
    },
    historyCardFooterValue: {
        color: colors.text,
        fontSize: 16,
        fontWeight: "800",
    },
    loaderWrap: {
        alignItems: "center",
        justifyContent: "center",
        minHeight: 180,
    },
    searchEmptyState: {
        alignItems: "center",
        flexGrow: 1,
        gap: spacing.sm,
        justifyContent: "center",
        minHeight: 320,
        paddingVertical: spacing.lg,
    },
    searchEmptyAnimation: {
        height: 180,
        width: 180,
    },
    searchEmptyText: {
        color: colors.mutedText,
        fontSize: 15,
        lineHeight: 22,
        maxWidth: 320,
        textAlign: "center",
    },
    searchEmptyLink: {
        color: colors.primary,
        fontSize: 15,
        fontWeight: "700",
    },
    searchEmptyLinkPressed: {
        opacity: 0.72,
    },
    footerLoaderWrap: {
        alignItems: "center",
        justifyContent: "center",
        paddingBottom: spacing.md,
        paddingTop: spacing.xs,
    },
    dateSheet: {
        backgroundColor: colors.background,
        borderTopLeftRadius: 24,
        borderTopRightRadius: 24,
        maxHeight: "72%",
        paddingBottom: spacing.md,
        paddingTop: spacing.md,
    },
    dateSheetHeader: {
        paddingHorizontal: spacing.md,
    },
    dateSheetBody: {
        gap: spacing.xs,
        paddingBottom: spacing.xs,
    },
    calendarWrap: {
        overflow: "hidden",
    },
    calendar: {
        alignSelf: "stretch",
    },
    filterActions: {
        flexDirection: "row",
        gap: spacing.sm,
        marginTop: 2,
        paddingHorizontal: spacing.md,
    },
    filterSecondaryButton: {
        alignItems: "center",
        borderRadius: 16,
        borderWidth: 1,
        borderColor: colors.border,
        flex: 1,
        justifyContent: "center",
        minHeight: 42,
        paddingHorizontal: spacing.md,
    },
    filterSecondaryButtonPressed: {
        opacity: 0.8,
    },
    filterSecondaryButtonText: {
        color: colors.text,
        fontSize: 15,
        fontWeight: "700",
    },
    filterPrimaryButton: {
        alignItems: "center",
        backgroundColor: colors.primary,
        borderRadius: 16,
        flex: 1,
        justifyContent: "center",
        minHeight: 42,
        paddingHorizontal: spacing.md,
    },
    filterPrimaryButtonPressed: {
        opacity: 0.88,
    },
    filterPrimaryButtonText: {
        color: "#ffffff",
        fontSize: 15,
        fontWeight: "800",
    },
})
