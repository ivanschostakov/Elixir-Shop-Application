import { Platform, StyleSheet } from "react-native"

import type { ThemePalette } from "@/theme/colors"
import { spacing } from "@/theme/spacing"

export const createProductScreenStyle = (colors: ThemePalette) => StyleSheet.create({
    screen: {
        flex: 1,
        backgroundColor: colors.surface,
        position: "relative",
    },
    container: {
        flex: 1,
        backgroundColor: colors.surface,
    },
    content: {
        backgroundColor: colors.pageBackground,
        flexGrow: 1,
        gap: spacing.md,
        paddingTop: spacing.md,
        paddingBottom: 0,
    },
    imageCard: {
        backgroundColor: colors.surface,
        borderRadius: spacing.lg,
        overflow: "hidden",
        width: "100%",
        ...Platform.select({
            web: {
                boxShadow: "0 8px 18px rgba(0, 0, 0, 0.06)",
            },
            default: {
                shadowColor: "#000000",
                shadowOffset: { width: 0, height: 8 },
                shadowOpacity: 0.06,
                shadowRadius: 18,
            },
        }),
        paddingBottom: spacing.xs,
    },
    image: {
        width: "100%",
        aspectRatio: 1,
        backgroundColor: colors.surfaceMuted,
        borderRadius: spacing.md,
    },
    priceInlineWrap: {
        paddingHorizontal: spacing.lg,
        paddingTop: spacing.xs,
    },
    priceInlineRow: {
        alignItems: "center",
        flexDirection: "row",
        flexWrap: "wrap",
        gap: spacing.xs,
    },
    priceInline: {
        color: colors.text,
        fontSize: 22,
        fontWeight: "800",
        lineHeight: 32,
    },
    priceInlineDiscounted: {
        color: colors.discountedPrice,
    },
    priceInlineOriginal: {
        color: colors.mutedText,
        fontSize: 17,
        fontWeight: "700",
        lineHeight: 26,
        textDecorationLine: "line-through",
    },
    priceInlinePercent: {
        color: colors.discountedPrice,
        fontSize: 17,
        fontWeight: "800",
        lineHeight: 26,
    },
    skuPressable: {
        alignSelf: "flex-start",
    },
    skuPressablePressed: {
        opacity: 0.72,
    },
    bookmarkButton: {
        alignItems: "center",
        justifyContent: "center",
        padding: 2,
    },
    headerActionsCluster: {
        alignItems: "center",
        flexDirection: "row",
        gap: 6,
        justifyContent: "flex-end",
    },
    headerActionButton: {
        alignItems: "center",
        backgroundColor: colors.surfaceOverlay,
        borderRadius: 12,
        height: 34,
        justifyContent: "center",
        width: 34,
    },
    imageActions: {
        alignItems: "center",
        flexDirection: "row",
        gap: 6,
        position: "absolute",
        right: spacing.sm,
        top: spacing.sm,
        zIndex: 2,
    },
    imageActionButton: {
        backgroundColor: colors.surfaceOverlay,
        borderRadius: 12,
        height: 34,
        width: 34,
    },
    shareIcon: {
        marginLeft: -1,
    },
    bookmarkButtonPressed: {
        opacity: 0.7,
        transform: [{ scale: 0.96 }],
    },
    bookmarkButtonDisabled: {
        opacity: 0.5,
    },
    screenshotSharePrompt: {
        backgroundColor: colors.surface,
        borderColor: colors.borderSoft,
        borderRadius: 18,
        borderWidth: 1,
        bottom: spacing.md,
        gap: spacing.sm,
        left: spacing.md,
        padding: spacing.md,
        position: "absolute",
        right: spacing.md,
        zIndex: 20,
    },
    screenshotSharePromptCopy: {
        gap: 4,
    },
    screenshotSharePromptTitle: {
        color: colors.text,
        fontSize: 15,
        fontWeight: "800",
        lineHeight: 20,
    },
    screenshotSharePromptDescription: {
        color: colors.mutedText,
        fontSize: 13,
        fontWeight: "600",
        lineHeight: 18,
    },
    screenshotSharePromptButton: {
        alignItems: "center",
        alignSelf: "flex-start",
        backgroundColor: colors.primary,
        borderRadius: 999,
        justifyContent: "center",
        minHeight: 36,
        paddingHorizontal: spacing.md,
    },
    screenshotSharePromptButtonPressed: {
        opacity: 0.76,
    },
    screenshotSharePromptButtonText: {
        color: colors.onPrimary,
        fontSize: 13,
        fontWeight: "800",
    },
    sectionStack: {
        flex: 1,
        gap: 0,
        width: "100%",
    },
    sectionWrap: {
        flex: 1,
        gap: 1,
        width: "100%",
    },
    recommendationStack: {
        gap: spacing.xl,
        paddingTop: spacing.md,
        width: "100%",
    },
    similarRailCard: {
        backgroundColor: colors.surface,
        borderRadius: spacing.lg,
        overflow: "hidden",
        paddingVertical: spacing.md,
        ...Platform.select({
            web: {
                boxShadow: "0 8px 16px rgba(0, 0, 0, 0.04)",
            },
            default: {
                shadowColor: "#000000",
                shadowOffset: { width: 0, height: 8 },
                shadowOpacity: 0.04,
                shadowRadius: 16,
            },
        }),
        width: "100%",
    },
    variantCard: {
        backgroundColor: colors.surface,
        borderRadius: spacing.lg,
        gap: 2,
        overflow: "hidden",
        paddingHorizontal: spacing.lg,
        paddingTop: spacing.sm,
        paddingBottom: spacing.sm,
        marginBottom: spacing.md,
        ...Platform.select({
            web: {
                boxShadow: "0 8px 16px rgba(0, 0, 0, 0.05)",
            },
            default: {
                shadowColor: "#000000",
                shadowOffset: { width: 0, height: 8 },
                shadowOpacity: 0.05,
                shadowRadius: 16,
            },
        }),
        width: "100%",
    },
    variantLabel: {
        color: colors.primary,
        fontSize: 10,
        fontWeight: "700",
        letterSpacing: 0.6,
        textTransform: "uppercase",
    },
    variantHeader: {
        alignItems: "flex-start",
        flexDirection: "row",
        gap: spacing.sm,
        justifyContent: "space-between",
        width: "100%",
    },
    variantHeaderCopy: {
        flex: 1,
        minWidth: 0,
    },
    variantTriggerValue: {
        color: colors.text,
        flexShrink: 1,
        fontSize: 16,
        fontWeight: "700",
    },
    variantTriggerStatus: {
        color: colors.mutedText,
        fontSize: 12,
        fontWeight: "600",
        lineHeight: 16,
    },
    variantSelectedLabel: {
        color: colors.text,
        fontSize: 15,
        fontWeight: "500",
        lineHeight: 20,
        marginTop: 0,
    },
    variantTriggerPrice: {
        color: colors.text,
        fontSize: 16,
        fontWeight: "800",
    },
    variantImageRow: {
        gap: spacing.sm,
        paddingTop: 0,
    },
    variantImageOption: {
        alignItems: "center",
        width: 72,
    },
    variantImageOptionSelected: {
        opacity: 1,
    },
    variantImageOptionDisabled: {
        opacity: 0.45,
    },
    variantImageOptionPressed: {
        opacity: 0.8,
    },
    variantImage: {
        backgroundColor: colors.surfaceMuted,
        borderRadius: 14,
        height: 72,
        width: 72,
    },
    variantImageName: {
        color: colors.text,
        fontSize: 11,
        fontWeight: "600",
        textAlign: "center",
        width: "100%",
    },
    variantImageSelectedBorder: {
        borderColor: colors.primary,
        borderWidth: 1,
    },
    sectionCard: {
        backgroundColor: colors.surface,
        borderRadius: spacing.lg,
        gap: spacing.xs,
        paddingHorizontal: spacing.lg,
        paddingTop: spacing.sm,
        paddingBottom: spacing.md,
        ...Platform.select({
            web: {
                boxShadow: "0 8px 16px rgba(0, 0, 0, 0.04)",
            },
            default: {
                shadowColor: "#000000",
                shadowOffset: { width: 0, height: 8 },
                shadowOpacity: 0.04,
                shadowRadius: 16,
            },
        }),
        width: "100%",
    },
    infoTabsHeader: {
        alignItems: "center",
        flexDirection: "row",
        gap: spacing.sm,
        justifyContent: "space-between",
    },
    infoTabsRail: {
        flex: 1,
        minWidth: 0,
        paddingBottom: 3,
        position: "relative",
    },
    infoTabsRow: {
        alignItems: "center",
        flexDirection: "row",
        justifyContent: "space-between",
        width: "100%",
    },
    infoTabButton: {
        alignItems: "center",
        justifyContent: "center",
        minHeight: 32,
        paddingBottom: 2,
        paddingHorizontal: 2,
        paddingTop: 2,
    },
    infoTabButtonText: {
        color: colors.mutedText,
        fontSize: 13,
        fontWeight: "700",
    },
    infoTabButtonTextActive: {
        color: colors.text,
    },
    infoTabIndicator: {
        backgroundColor: colors.primary,
        borderRadius: 999,
        bottom: 0,
        height: 3,
        left: 0,
        position: "absolute",
    },
    infoTabContent: {
        marginTop: spacing.xs,
    },
    sectionCardLast: {
        borderBottomWidth: 0,
        flex: 1,
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
    sectionHeaderRow: {
        alignItems: "flex-start",
        flexDirection: "row",
        gap: spacing.md,
        justifyContent: "space-between",
    },
    sectionHeaderCopy: {
        flex: 1,
        gap: spacing.xs,
    },
    sectionDescription: {
        color: colors.mutedText,
        fontSize: 14,
        lineHeight: 22,
    },
    sectionBody: {
        color: colors.mutedText,
        fontSize: 16,
        lineHeight: 24,
    },
    detailsList: {
        marginTop: spacing.xs,
    },
    detailRow: {
        gap: spacing.xs,
        paddingVertical: spacing.md,
    },
    detailLabel: {
        color: colors.mutedText,
        fontSize: 12,
        fontWeight: "700",
        letterSpacing: 0.6,
        textTransform: "uppercase",
    },
    detailValue: {
        color: colors.text,
        fontSize: 16,
        fontWeight: "600",
        lineHeight: 24,
    },
    detailRichText: {
        color: colors.text,
        fontSize: 16,
        lineHeight: 24,
    },
    detailValueSku: {
        color: colors.primary,
    },
    detailDivider: {
        backgroundColor: colors.border,
        height: 1,
    },
    reviewsPlaceholder: {
        gap: spacing.sm,
    },
    reviewWriteLabel: {
        alignSelf: "flex-start",
        color: colors.primary,
        fontSize: 14,
        fontWeight: "700",
        textTransform: "uppercase",
    },
    reviewComposer: {
        backgroundColor: colors.surfaceMuted,
        borderRadius: spacing.md,
        gap: spacing.sm,
        padding: spacing.sm,
    },
    reviewRatingOptionsRow: {
        flexDirection: "row",
        gap: spacing.xs,
    },
    reviewRatingOption: {
        alignItems: "center",
        backgroundColor: colors.surface,
        borderColor: colors.border,
        borderRadius: 999,
        borderWidth: 1,
        minWidth: 34,
        paddingHorizontal: spacing.sm,
        paddingVertical: 6,
    },
    reviewRatingOptionActive: {
        backgroundColor: colors.primary,
        borderColor: colors.primary,
    },
    reviewRatingOptionPressed: {
        opacity: 0.8,
    },
    reviewRatingOptionText: {
        color: colors.text,
        fontSize: 13,
        fontWeight: "700",
    },
    reviewRatingOptionTextActive: {
        color: colors.onPrimary,
    },
    reviewComposerInput: {
        backgroundColor: colors.surface,
        borderColor: colors.border,
        borderRadius: spacing.sm,
        borderWidth: 1,
        color: colors.text,
        fontSize: 14,
        minHeight: 90,
        paddingHorizontal: spacing.sm,
        paddingVertical: spacing.sm,
        textAlignVertical: "top",
    },
    reviewSubmitButton: {
        alignItems: "center",
        alignSelf: "flex-start",
        backgroundColor: colors.primary,
        borderRadius: 999,
        justifyContent: "center",
        minHeight: 36,
        paddingHorizontal: spacing.md,
    },
    reviewSubmitButtonDisabled: {
        opacity: 0.6,
    },
    reviewSubmitButtonPressed: {
        opacity: 0.82,
    },
    reviewSubmitButtonText: {
        color: colors.onPrimary,
        fontSize: 13,
        fontWeight: "800",
    },
    reviewPhotoButton: {
        alignItems: "center",
        borderColor: colors.border,
        borderRadius: 12,
        borderWidth: 1,
        justifyContent: "center",
        minHeight: 38,
        paddingHorizontal: 12,
    },
    reviewPhotoButtonPressed: {
        opacity: 0.8,
    },
    reviewPhotoButtonText: {
        color: colors.text,
        fontSize: 13,
        fontWeight: "700",
    },
    reviewAttachmentPreviewRow: {
        flexDirection: "row",
        flexWrap: "wrap",
        gap: spacing.xs,
    },
    reviewAttachmentPreviewTile: {
        borderRadius: 10,
        overflow: "hidden",
    },
    reviewAttachmentPreviewImage: {
        width: 56,
        height: 56,
        backgroundColor: colors.surfaceMuted,
    },
    reviewSubmitError: {
        color: colors.danger,
        fontSize: 12,
        fontWeight: "600",
        lineHeight: 16,
    },
    reviewCard: {
        backgroundColor: colors.surfaceMuted,
        borderRadius: spacing.md,
        gap: spacing.xs,
        padding: spacing.sm,
    },
    reviewCardHeader: {
        alignItems: "center",
        flexDirection: "row",
        justifyContent: "space-between",
    },
    reviewCardAuthor: {
        color: colors.text,
        fontSize: 12,
        fontWeight: "700",
    },
    reviewCardRating: {
        color: colors.text,
        fontSize: 14,
        fontWeight: "700",
    },
    reviewCardRatingRow: {
        alignItems: "center",
        flexDirection: "row",
        gap: 6,
    },
    reviewCardText: {
        color: colors.text,
        fontSize: 14,
        lineHeight: 20,
    },
    reviewCardAttachmentsRow: {
        flexDirection: "row",
        flexWrap: "wrap",
        gap: spacing.xs,
        marginTop: 2,
    },
    reviewCardAttachmentImage: {
        width: 84,
        height: 84,
        borderRadius: 10,
        backgroundColor: colors.surface,
    },
    reviewsSummaryRow: {
        alignItems: "center",
        flexDirection: "row",
        gap: 6,
    },
    ratingStarsRow: {
        alignItems: "center",
        flexDirection: "row",
        gap: 2,
    },
    ratingStarSlot: {
        overflow: "hidden",
        position: "relative",
    },
    ratingStarFillOverlay: {
        left: 0,
        overflow: "hidden",
        position: "absolute",
        top: 0,
    },
    reviewsSummaryValue: {
        color: colors.text,
        fontSize: 18,
        fontWeight: "800",
    },
    stateContainer: {
        flex: 1,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: colors.background,
        paddingHorizontal: spacing.md,
    },
    stateText: {
        fontSize: 16,
        color: colors.text,
        textAlign: "center",
    },
})
