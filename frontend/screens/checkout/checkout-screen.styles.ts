import { StyleSheet } from "react-native"

import { colors } from "@/theme/colors"
import { spacing } from "@/theme/spacing"

export const checkoutScreenStyles = StyleSheet.create({
    container: {
        backgroundColor: "#F3F5F8",
        flex: 1,
    },
    scrollView: {
        backgroundColor: "#F3F5F8",
        flex: 1,
    },
    content: {
        gap: spacing.md,
        paddingHorizontal: 0,
        paddingTop: 0,
        paddingBottom: 0,
    },
    stateCard: {
        backgroundColor: colors.surface,
        borderRadius: spacing.lg,
        gap: spacing.md,
        padding: spacing.lg,
        width: "100%",
    },
    stateCardTop: {
        borderTopLeftRadius: 0,
        borderTopRightRadius: 0,
    },
    stateCardBottom: {
        borderBottomLeftRadius: 0,
        borderBottomRightRadius: 0,
    },
    stateLoadingRow: {
        alignItems: "center",
        gap: spacing.sm,
        justifyContent: "center",
        minHeight: 160,
        padding: spacing.lg,
    },
    sectionTitle: {
        color: colors.text,
        fontSize: 16,
        fontWeight: "800",
        lineHeight: 20,
    },
    stateText: {
        color: colors.mutedText,
        fontSize: 15,
        lineHeight: 22,
    },
    detailsSheetCard: {
        backgroundColor: colors.surface,
        borderRadius: spacing.lg,
        borderTopLeftRadius: 0,
        borderTopRightRadius: 0,
        overflow: "hidden",
        paddingHorizontal: 0,
        paddingTop: 0,
        paddingBottom: spacing.sm,
    },
    detailsSheetRow: {
        alignItems: "center",
        flexDirection: "row",
        gap: 6,
        minHeight: 64,
        paddingHorizontal: spacing.lg,
        paddingVertical: 10,
    },
    detailsSheetRowPressed: {
        opacity: 0.82,
    },
    detailsSheetDivider: {
        backgroundColor: "rgba(17,17,17,0.08)",
        height: 1,
        marginHorizontal: spacing.lg,
    },
    detailsSheetLabel: {
        color: colors.text,
        flexShrink: 0,
        fontSize: 14,
        fontWeight: "700",
        lineHeight: 17,
        width: 86,
    },
    detailsSheetTrailing: {
        alignItems: "center",
        flex: 1,
        flexDirection: "row",
        justifyContent: "flex-end",
    },
    detailsSheetTextBlock: {
        alignItems: "flex-end",
        flex: 1,
        justifyContent: "center",
        minWidth: 0,
        paddingVertical: 2,
    },
    detailsSheetPrimary: {
        color: colors.text,
        fontSize: 14,
        fontWeight: "400",
        lineHeight: 17,
        maxWidth: "100%",
        textAlign: "right",
    },
    detailsSheetSecondary: {
        color: colors.text,
        fontSize: 14,
        fontWeight: "400",
        lineHeight: 17,
        maxWidth: "100%",
        textAlign: "right",
    },
    detailsSheetInput: {
        color: colors.text,
        fontSize: 14,
        fontWeight: "400",
        lineHeight: 17,
        minHeight: 24,
        paddingHorizontal: 0,
        paddingVertical: 0,
        textAlign: "right",
        width: "100%",
    },
    selectorPanel: {
        gap: 6,
        paddingTop: 6,
        paddingBottom: 8,
    },
    selectorLoadingRow: {
        alignItems: "center",
        justifyContent: "center",
        minHeight: 28,
    },
    selectorPickerWrap: {
        backgroundColor: "#f7f9fc",
        borderRadius: 14,
        marginTop: 2,
        overflow: "hidden",
    },
    selectorPicker: {
        color: colors.text,
        marginHorizontal: -6,
    },
    selectorEditor: {
        gap: 6,
        marginTop: 2,
    },
    selectorInput: {
        backgroundColor: "#f7f9fc",
        borderRadius: 12,
        color: colors.text,
        fontSize: 13,
        minHeight: 38,
        paddingHorizontal: 10,
    },
    selectorSaveButton: {
        alignItems: "center",
        backgroundColor: colors.text,
        borderRadius: 12,
        justifyContent: "center",
        minHeight: 38,
        paddingHorizontal: 12,
    },
    selectorSaveButtonPressed: {
        opacity: 0.88,
    },
    selectorSaveButtonText: {
        color: colors.surface,
        fontSize: 13,
        fontWeight: "700",
        lineHeight: 17,
    },
    recipientEditorSheet: {
        gap: 18,
        paddingBottom: 20,
        paddingTop: 12,
    },
    recipientEditorHeader: {
        alignItems: "flex-start",
        flexDirection: "row",
        gap: 12,
        justifyContent: "space-between",
    },
    recipientEditorTitle: {
        color: colors.text,
        flex: 1,
        fontSize: 20,
        fontWeight: "800",
        lineHeight: 26,
    },
    recipientEditorCloseButton: {
        alignItems: "center",
        height: 36,
        justifyContent: "center",
        width: 36,
    },
    recipientEditorCloseButtonPressed: {
        opacity: 0.72,
    },
    recipientEditorCloseText: {
        color: colors.mutedText,
        fontSize: 28,
        fontWeight: "400",
        lineHeight: 28,
    },
    recipientEditorFields: {
        gap: 12,
    },
    recipientEditorFieldWrap: {
        gap: 6,
    },
    recipientEditorInput: {
        backgroundColor: "#f4f7fb",
        borderRadius: 20,
        color: colors.text,
        fontSize: 16,
        lineHeight: 20,
        minHeight: 72,
        paddingHorizontal: 22,
        paddingVertical: 18,
    },
    recipientEditorInputError: {
        borderColor: "#dc4a4a",
        borderWidth: 1,
    },
    recipientEditorFieldError: {
        color: "#dc4a4a",
        fontSize: 13,
        fontWeight: "600",
        lineHeight: 16,
        paddingHorizontal: 8,
    },
    recipientEditorSubmitButton: {
        alignItems: "center",
        backgroundColor: colors.primary,
        borderRadius: 18,
        justifyContent: "center",
        minHeight: 56,
        paddingHorizontal: 18,
    },
    recipientEditorSubmitButtonDisabled: {
        backgroundColor: "#dbe9f8",
    },
    recipientEditorSubmitButtonPressed: {
        opacity: 0.88,
    },
    recipientEditorSubmitButtonText: {
        color: colors.surface,
        fontSize: 16,
        fontWeight: "700",
        lineHeight: 20,
    },
    recipientEditorSubmitButtonTextDisabled: {
        color: "#8ea4bd",
    },
    compactSection: {
        gap: spacing.sm,
    },
    sectionCard: {
        backgroundColor: "#FFFFFF",
        borderRadius: spacing.lg,
        gap: spacing.sm,
        paddingHorizontal: 0,
        paddingTop: spacing.sm,
        paddingBottom: spacing.md,
        width: "100%",
    },
    positionsSectionCard: {
        paddingBottom: spacing.sm,
    },
    sectionHeader: {
        alignItems: "center",
        flexDirection: "row",
        justifyContent: "space-between",
        marginBottom: spacing.xs,
        paddingHorizontal: spacing.lg,
    },
    sectionHeaderTitle: {
        color: colors.text,
        fontSize: 22,
        fontWeight: "800",
        lineHeight: 30,
    },
    sectionHeaderActionButton: {
        alignItems: "center",
        height: 34,
        justifyContent: "center",
        width: 34,
    },
    sectionHeaderActionButtonPressed: {
        opacity: 0.72,
    },
    sectionHeaderActionButtonDisabled: {
        opacity: 0.5,
    },
    sectionHeaderActionButtonText: {
        color: colors.text,
        fontSize: 24,
        fontWeight: "400",
        lineHeight: 24,
        marginTop: -2,
    },
    positionsCarousel: {
        flexGrow: 0,
    },
    positionsCarouselContent: {
        gap: 12,
        paddingHorizontal: spacing.lg,
    },
    positionCard: {
        backgroundColor: "transparent",
        width: 156,
    },
    positionImage: {
        aspectRatio: 1,
        borderRadius: 18,
        width: "100%",
    },
    positionInfo: {
        gap: 2,
        marginTop: spacing.sm,
    },
    positionTitle: {
        color: colors.text,
        fontSize: 14,
        fontWeight: "700",
        lineHeight: 18,
    },
    positionSubtitle: {
        color: colors.mutedText,
        fontSize: 12,
        lineHeight: 16,
    },
    positionPrice: {
        color: colors.text,
        fontSize: 14,
        fontWeight: "800",
        lineHeight: 18,
        marginTop: 2,
    },
    totalsList: {
        gap: spacing.sm,
        marginTop: 0,
        paddingHorizontal: spacing.lg,
    },
    totalRow: {
        alignItems: "center",
        flexDirection: "row",
        justifyContent: "space-between",
        minHeight: 22,
    },
    totalRowGrandTotal: {
        marginBottom: spacing.xs,
    },
    totalLabel: {
        color: colors.mutedText,
        fontSize: 14,
        lineHeight: 20,
    },
    totalValue: {
        color: colors.text,
        fontSize: 14,
        fontWeight: "700",
        lineHeight: 20,
    },
    totalLabelStrong: {
        color: colors.text,
        fontSize: 16,
        fontWeight: "800",
        lineHeight: 22,
    },
    totalValueStrong: {
        color: colors.text,
        fontSize: 18,
        fontWeight: "900",
        lineHeight: 24,
    },
    summaryDivider: {
        backgroundColor: colors.border,
        height: 1,
        marginHorizontal: spacing.lg,
        marginVertical: spacing.xs,
    },
    summaryActions: {
        gap: spacing.sm,
        paddingHorizontal: spacing.lg,
    },
    infoList: {
        gap: spacing.sm,
    },
    infoRow: {
        gap: 4,
    },
    infoLabel: {
        color: colors.mutedText,
        fontSize: 12,
        fontWeight: "700",
        letterSpacing: 0.35,
        textTransform: "uppercase",
    },
    infoValue: {
        color: colors.text,
        fontSize: 15,
        fontWeight: "600",
        lineHeight: 21,
    },
    actionRow: {
        flexDirection: "row",
        gap: spacing.sm,
    },
    actionRowSingle: {
        flexDirection: "column",
    },
    secondaryButton: {
        alignItems: "center",
        backgroundColor: "#F7F9FC",
        borderColor: "rgba(17,17,17,0.12)",
        borderRadius: 18,
        borderWidth: 1,
        justifyContent: "center",
        minHeight: 52,
        paddingHorizontal: spacing.md,
    },
    secondaryButtonFullWidth: {
        width: "100%",
    },
    secondaryButtonPressed: {
        opacity: 0.72,
    },
    secondaryButtonDisabled: {
        opacity: 0.5,
    },
    secondaryButtonText: {
        color: colors.text,
        fontSize: 14,
        fontWeight: "700",
    },
    loadingText: {
        color: colors.mutedText,
        fontSize: 14,
        lineHeight: 20,
        marginTop: spacing.sm,
    },
    footerCtaButton: {
        alignItems: "center",
        backgroundColor: colors.primary,
        borderRadius: 16,
        justifyContent: "center",
        minHeight: 56,
        paddingHorizontal: spacing.md,
        width: "100%",
    },
    footerCtaButtonDisabled: {
        backgroundColor: "#DCE8F5",
    },
    footerCtaButtonPressed: {
        opacity: 0.88,
    },
    footerCtaButtonText: {
        color: colors.surface,
        fontSize: 18,
        fontWeight: "800",
        lineHeight: 22,
    },
    footerCtaButtonTextDisabled: {
        color: "#7E97B4",
    },
    footerActionStack: {
        gap: spacing.xs,
    },
    footerTotalsList: {
        gap: spacing.xs,
        paddingHorizontal: spacing.xs,
        paddingTop: spacing.xs,
    },
})
