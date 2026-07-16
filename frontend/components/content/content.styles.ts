import { StyleSheet } from "react-native"

import type { ThemePalette } from "@/theme/colors"
import { spacing } from "@/theme/spacing"

export const createContentStyles = (colors: ThemePalette) => StyleSheet.create({
    railSection: {
        gap: spacing.md,
    },
    railGrid: {
        flexDirection: "row",
        flexWrap: "wrap",
        gap: spacing.sm,
        paddingHorizontal: spacing.md,
    },
    railGridDiscover: {
        gap: spacing.sm,
    },
    railGridDiscoverRow: {
        backgroundColor: colors.surface,
        borderRadius: 28,
        flexDirection: "row",
        justifyContent: "space-between",
        overflow: "hidden",
        width: "100%",
    },
    railGridDiscoverMergedCard: {
        backgroundColor: colors.surface,
        borderRadius: 28,
        overflow: "hidden",
        width: "100%",
    },
    railGridDiscoverMergedHeader: {
        paddingBottom: spacing.sm,
        paddingTop: spacing.md,
    },
    railGridDiscoverMergedFirstRow: {
        borderTopLeftRadius: 0,
        borderTopRightRadius: 0,
    },
    railGridDiscoverItem: {
        flex: 1,
    },
    railGridDiscoverSpacer: {
        flex: 1,
    },
    railGridDiscoverCard: {
        borderRadius: 0,
        overflow: "visible",
    },
    railGridItem: {
        width: "47.5%",
    },
    railLoaderWrap: {
        alignItems: "center",
        justifyContent: "center",
        minHeight: 48,
    },
    sectionHeader: {
        alignItems: "flex-end",
        flexDirection: "row",
        gap: spacing.md,
        justifyContent: "space-between",
        paddingHorizontal: spacing.md,
    },
    sectionHeaderCopy: {
        flex: 1,
        gap: spacing.xs,
        minWidth: 0,
    },
    sectionEyebrow: {
        color: colors.primary,
        fontSize: 11,
        fontWeight: "700",
        letterSpacing: 0.8,
        textTransform: "uppercase",
    },
    sectionTitle: {
        color: colors.text,
        fontSize: 24,
        fontWeight: "800",
    },
    sectionDescription: {
        color: colors.mutedText,
        fontSize: 14,
        lineHeight: 20,
    },
    sectionAction: {
        borderRadius: 999,
        paddingHorizontal: spacing.sm,
        paddingVertical: spacing.xs,
    },
    sectionActionPressed: {
        opacity: 0.72,
    },
    sectionActionText: {
        color: colors.primary,
        fontSize: 14,
        fontWeight: "700",
    },
    topTabBar: {
        alignSelf: "center",
        flexDirection: "row",
        gap: spacing.md,
        position: "relative",
    },
    topTabButton: {
        alignItems: "center",
        minWidth: 76,
        paddingBottom: 6,
        paddingHorizontal: spacing.xs,
        paddingTop: 2,
    },
    topTabButtonPressed: {
        opacity: 0.72,
    },
    topTabLabel: {
        color: colors.mutedText,
        fontSize: 15,
        fontWeight: "700",
    },
    topTabLabelOnColor: {
        color: "rgba(255, 255, 255, 0.78)",
    },
    topTabLabelActive: {
        color: colors.text,
        fontWeight: "800",
    },
    topTabLabelActiveOnColor: {
        color: "#FFFFFF",
    },
    topTabIndicator: {
        backgroundColor: colors.primary,
        borderRadius: 999,
        bottom: 0,
        height: 3,
        left: 0,
        position: "absolute",
    },
    topTabIndicatorOnColor: {
        backgroundColor: "#FFFFFF",
    },
    browseControls: {
        flexDirection: "row",
        gap: spacing.sm,
    },
    browseControlsRow: {
        alignItems: "flex-start",
        alignSelf: "stretch",
        flexDirection: "row",
        gap: spacing.md,
        justifyContent: "space-between",
        width: "100%",
    },
    browseSection: {
        gap: spacing.xs,
    },
    browseSectionCompact: {
        flex: 1,
        flexShrink: 1,
        gap: 2,
        minWidth: 112,
    },
    browseSectionCompactEnd: {
        alignItems: "flex-end",
        flex: 0,
        marginLeft: "auto",
    },
    browseSectionLabel: {
        color: colors.stateText,
        fontSize: 11,
        fontWeight: "700",
        letterSpacing: 1,
        textTransform: "uppercase",
    },
    browseSectionLabelEnd: {
        textAlign: "right",
    },
    browseTrigger: {
        alignSelf: "flex-start",
        borderBottomColor: "transparent",
        borderBottomWidth: 0,
        paddingBottom: 0,
    },
    browseTriggerEnd: {
        alignSelf: "flex-end",
    },
    browseTriggerPressed: {
        opacity: 0.72,
    },
    browseTriggerActive: {
        borderBottomColor: "transparent",
    },
    browseTriggerValue: {
        color: colors.text,
        fontSize: 16,
        fontWeight: "700",
    },
    browseTriggerValueActive: {
        color: colors.primary,
    },
    browseTriggerPlaceholderValue: {
        color: colors.mutedText,
    },
    browsePickerBackdrop: {
        backgroundColor: "rgba(17, 24, 39, 0.38)",
        flex: 1,
        justifyContent: "flex-end",
    },
    browsePickerDismissArea: {
        flex: 1,
    },
    browsePickerSheet: {
        backgroundColor: colors.surface,
        borderTopLeftRadius: 24,
        borderTopRightRadius: 24,
        paddingBottom: spacing.lg,
        paddingHorizontal: spacing.md,
        paddingTop: spacing.md,
    },
    browsePickerHeader: {
        alignItems: "center",
        flexDirection: "row",
        justifyContent: "space-between",
        marginBottom: spacing.sm,
    },
    browsePickerTitle: {
        color: colors.text,
        fontSize: 18,
        fontWeight: "800",
    },
    browsePickerActions: {
        flexDirection: "row",
        gap: spacing.sm,
    },
    browsePickerAction: {
        alignItems: "center",
        justifyContent: "center",
        minHeight: 36,
        paddingHorizontal: spacing.sm,
    },
    browsePickerPrimaryAction: {
        alignItems: "center",
        backgroundColor: colors.primaryMuted,
        borderRadius: 999,
        justifyContent: "center",
        minHeight: 36,
        paddingHorizontal: spacing.sm,
    },
    browsePickerActionPressed: {
        opacity: 0.72,
    },
    browsePickerActionText: {
        color: colors.mutedText,
        fontSize: 14,
        fontWeight: "700",
    },
    browsePickerPrimaryActionText: {
        color: colors.primary,
        fontSize: 14,
        fontWeight: "800",
    },
    browsePicker: {
        marginHorizontal: -spacing.sm,
    },
    productCard: {
        backgroundColor: colors.surface,
        borderRadius: 24,
        flex: 1,
        overflow: "hidden",
    },
    productCardContent: {
        flex: 1,
    },
    productCardPressed: {
        opacity: 0.92,
        transform: [{ scale: 0.99 }],
    },
    productImageWrap: {
        overflow: "hidden",
        position: "relative",
    },
    productImage: {
        aspectRatio: 1,
        backgroundColor: colors.surfaceMuted,
        width: "100%",
    },
    productImageOutOfStockOverlay: {
        alignItems: "center",
        backgroundColor: "rgba(233, 104, 124, 0.05)",
        bottom: 0,
        justifyContent: "center",
        left: 0,
        position: "absolute",
        right: 0,
        top: 0,
    },
    productImageOutOfStockBadge: {
        alignItems: "center",
        backgroundColor: colors.surfaceOverlaySoft,
        borderRadius: 999,
        justifyContent: "center",
        maxWidth: "82%",
        paddingHorizontal: spacing.md,
        paddingVertical: spacing.sm,
    },
    productImageOutOfStockText: {
        color: "rgba(183, 63, 86, 0.95)",
        fontSize: 14,
        fontWeight: "800",
        textAlign: "center",
        textTransform: "uppercase",
    },
    productBody: {
        gap: 2,
        paddingHorizontal: 10,
        paddingBottom: 8,
        paddingTop: 8,
    },
    productMetaWrap: {
        paddingBottom: 8,
        paddingHorizontal: 10,
    },
    productEyebrow: {
        color: colors.primary,
        fontSize: 11,
        fontWeight: "700",
        letterSpacing: 0.6,
        textTransform: "uppercase",
    },
    productTitle: {
        color: colors.text,
        fontSize: 12,
        fontWeight: "700",
        lineHeight: 16,
    },
    productPriceRow: {
        alignItems: "flex-start",
        flexDirection: "row",
        gap: 8,
        justifyContent: "space-between",
        minHeight: 34,
    },
    productPriceBlock: {
        flex: 1,
        gap: 1,
        minWidth: 0,
    },
    productPrice: {
        color: colors.text,
        fontSize: 14,
        flexShrink: 1,
        fontWeight: "800",
        lineHeight: 18,
    },
    productPriceDiscounted: {
        color: colors.discountedPrice,
    },
    productDiscountMetaRow: {
        alignItems: "center",
        flexDirection: "row",
        flexWrap: "wrap",
        gap: 5,
        minHeight: 14,
    },
    productOriginalPrice: {
        color: colors.mutedText,
        fontSize: 11,
        fontWeight: "700",
        lineHeight: 14,
        textDecorationLine: "line-through",
    },
    productDiscountPercent: {
        color: colors.discountedPrice,
        fontSize: 11,
        fontWeight: "800",
        lineHeight: 14,
    },
    productRatingRow: {
        alignItems: "center",
        flexDirection: "row",
        gap: 4,
        flexShrink: 0,
        paddingTop: 3,
    },
    productRatingValue: {
        color: colors.text,
        fontSize: 11,
        fontWeight: "700",
    },
    productRatingCount: {
        color: colors.mutedText,
        fontSize: 10,
        fontWeight: "600",
    },
    productSubtitle: {
        color: colors.mutedText,
        fontSize: 12,
        lineHeight: 15,
    },
    productMetaBadge: {
        alignSelf: "flex-start",
        backgroundColor: colors.primaryMuted,
        borderRadius: 999,
        paddingHorizontal: 6,
        paddingVertical: 4,
    },
    productMetaBadgeText: {
        color: colors.primary,
        fontSize: 10,
        fontWeight: "700",
    },
    productMetaBadgePressed: {
        opacity: 0.72,
    },
    listCard: {
        alignItems: "center",
        backgroundColor: colors.surface,
        borderRadius: 24,
        flexDirection: "row",
        gap: spacing.md,
        marginHorizontal: spacing.md,
        minHeight: 108,
        overflow: "hidden",
        padding: 12,
    },
    listCardContent: {
        flex: 1,
        gap: spacing.xs,
        minWidth: 0,
    },
    listCardMain: {
        alignItems: "center",
        flexDirection: "row",
        gap: spacing.md,
        minWidth: 0,
    },
    listCardPressed: {
        opacity: 0.82,
    },
    listCardImage: {
        backgroundColor: colors.surfaceMuted,
        borderRadius: 18,
        height: 84,
        width: 84,
    },
    listCardBody: {
        flex: 1,
        gap: spacing.xs,
        minWidth: 0,
    },
    listCardEyebrow: {
        color: colors.primary,
        fontSize: 11,
        fontWeight: "700",
        letterSpacing: 0.6,
        textTransform: "uppercase",
    },
    listCardTitle: {
        color: colors.text,
        fontSize: 17,
        fontWeight: "700",
    },
    listCardSubtitle: {
        color: colors.mutedText,
        fontSize: 14,
        lineHeight: 20,
    },
    listCardRatingRow: {
        alignItems: "center",
        flexDirection: "row",
        gap: 4,
    },
    listCardRatingValue: {
        color: colors.text,
        fontSize: 12,
        fontWeight: "700",
    },
    listCardRatingCount: {
        color: colors.mutedText,
        fontSize: 11,
        fontWeight: "600",
    },
    listCardMeta: {
        color: colors.primary,
        fontSize: 12,
        fontWeight: "700",
        letterSpacing: 0.4,
        textTransform: "uppercase",
    },
    listCardMetaPressed: {
        opacity: 0.72,
    },
    listCardAction: {
        alignItems: "center",
        justifyContent: "center",
    },
    emptyState: {
        alignItems: "center",
        backgroundColor: colors.surface,
        borderColor: colors.border,
        borderRadius: 28,
        borderWidth: 1,
        gap: spacing.sm,
        marginHorizontal: spacing.md,
        paddingHorizontal: spacing.lg,
        paddingVertical: spacing.xl,
    },
    emptyStateBorderless: {
        borderWidth: 0,
    },
    emptyStatePlain: {
        backgroundColor: "transparent",
        borderWidth: 0,
        marginHorizontal: 0,
        paddingHorizontal: 0,
        paddingVertical: 0,
    },
    emptyStateIllustration: {
        height: 132,
        marginBottom: spacing.xs,
        width: 132,
    },
    emptyStateIllustrationLarge: {
        height: 180,
        width: 180,
    },
    emptyStateIllustrationWrap: {
        alignItems: "center",
        justifyContent: "center",
        marginBottom: spacing.xs,
    },
    emptyStateEyebrow: {
        color: colors.primary,
        fontSize: 11,
        fontWeight: "700",
        letterSpacing: 0.8,
        textTransform: "uppercase",
    },
    emptyStateTitle: {
        color: colors.text,
        fontSize: 22,
        fontWeight: "800",
        textAlign: "center",
    },
    emptyStateDescription: {
        color: colors.mutedText,
        fontSize: 15,
        lineHeight: 24,
        textAlign: "center",
    },
    emptyStateAction: {
        alignItems: "center",
        backgroundColor: colors.primary,
        borderRadius: 999,
        justifyContent: "center",
        marginTop: spacing.xs,
        minHeight: 46,
        paddingHorizontal: spacing.lg,
    },
    emptyStateActionPressed: {
        opacity: 0.82,
    },
    emptyStateActionText: {
        color: "#ffffff",
        fontSize: 15,
        fontWeight: "700",
    },
    emptyStateActionLink: {
        alignItems: "center",
        justifyContent: "center",
        marginTop: spacing.xs,
        minHeight: 28,
    },
    emptyStateActionLinkText: {
        color: colors.primary,
        fontSize: 15,
        fontWeight: "700",
    },
})
