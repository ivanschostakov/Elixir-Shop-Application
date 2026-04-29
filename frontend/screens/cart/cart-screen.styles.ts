import { StyleSheet } from "react-native"
import { colors } from "@/theme/colors"
import { spacing } from "@/theme/spacing"

export const cartScreenStyles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: colors.pageBackground,
    },
    emptyContainer: {
        backgroundColor: colors.surface,
    },
    emptyContent: {
        alignItems: "center",
        flex: 1,
        justifyContent: "center",
        paddingHorizontal: spacing.md,
    },
    loadingContainer: {
        backgroundColor: colors.pageBackground,
        flex: 1,
    },
    errorContainer: {
        backgroundColor: colors.pageBackground,
        flex: 1,
    },
    stateScrollContent: {
        paddingHorizontal: 0,
        paddingTop: 0,
        paddingBottom: 0,
    },
    stateCard: {
        backgroundColor: colors.surface,
        borderBottomLeftRadius: 0,
        borderBottomRightRadius: 0,
        borderTopLeftRadius: 0,
        borderTopRightRadius: 0,
        gap: spacing.md,
        paddingHorizontal: spacing.lg,
        paddingVertical: spacing.lg,
        width: "100%",
    },
    stateLoadingRow: {
        alignItems: "center",
        gap: spacing.sm,
        justifyContent: "center",
        minHeight: 160,
    },
    errorTitle: {
        color: colors.text,
        fontSize: 22,
        fontWeight: "800",
        textAlign: "center",
    },
    errorText: {
        color: colors.mutedText,
        fontSize: 15,
        lineHeight: 22,
        textAlign: "center",
    },
    retryButton: {
        alignItems: "center",
        backgroundColor: colors.primary,
        borderRadius: 14,
        justifyContent: "center",
        marginTop: spacing.sm,
        minHeight: 48,
        paddingHorizontal: spacing.lg,
    },
    retryButtonText: {
        color: colors.onPrimary,
        fontSize: 15,
        fontWeight: "700",
    },
    headerSaveButton: {
        alignItems: "center",
        justifyContent: "center",
        minHeight: 34,
        paddingRight: spacing.xs,
    },
    headerSaveButtonPressed: {
        opacity: 0.5,
    },
    headerSaveButtonDisabled: {
        opacity: 0.45,
    },
    scrollContent: {
        gap: spacing.md,
        paddingHorizontal: 0,
        paddingTop: 0,
        paddingBottom: 0,
    },
    sectionTop: {
        borderTopLeftRadius: 0,
        borderTopRightRadius: 0,
    },
    sectionBottom: {
        borderBottomLeftRadius: 0,
        borderBottomRightRadius: 0,
    },
    summarySection: {
        backgroundColor: colors.surface,
        borderRadius: spacing.lg,
        overflow: "hidden",
    },
    summaryCard: {
        gap: spacing.sm,
        paddingHorizontal: spacing.lg,
        paddingTop: spacing.sm,
        paddingBottom: spacing.sm,
    },
    summaryStats: {
        flexDirection: "row",
        gap: spacing.sm,
    },
    summaryFooter: {
        borderTopColor: colors.border,
        borderTopWidth: 1,
        gap: spacing.xs,
        paddingHorizontal: spacing.lg,
        paddingBottom: spacing.sm,
        paddingTop: spacing.sm,
    },
    summaryStat: {
        flex: 1,
        gap: 2,
        paddingHorizontal: spacing.xs,
        paddingVertical: 0,
    },
    summaryStatStart: {
        alignItems: "flex-start",
    },
    summaryStatEnd: {
        alignItems: "flex-end",
    },
    summaryStatLabel: {
        color: colors.mutedText,
        fontSize: 10,
        fontWeight: "700",
        textTransform: "uppercase",
    },
    summaryStatValue: {
        color: colors.text,
        fontSize: 16,
        fontWeight: "800",
    },
    summaryStatValuePrice: {
        color: colors.text,
    },
    promoInput: {
        backgroundColor: colors.surfaceElevated,
        borderRadius: 10,
        color: colors.text,
        fontSize: 14,
        minHeight: 40,
        paddingHorizontal: spacing.sm,
    },
    deliveryCountryCarousel: {
        marginBottom: spacing.xs,
    },
    deliveryCountryCarouselContent: {
        gap: spacing.sm,
        paddingRight: spacing.xs,
    },
    deliveryCountryButton: {
        alignItems: "center",
        justifyContent: "center",
        opacity: 1,
    },
    deliveryCountryButtonInactive: {
        opacity: 0.38,
    },
    deliveryCountryButtonPressed: {
        opacity: 0.7,
    },
    deliveryCountryFlag: {
        height: 32,
        width: 32,
    },
    deliveryPointCard: {
        backgroundColor: colors.surfaceElevated,
        borderColor: colors.border,
        borderRadius: 16,
        borderWidth: 1,
        gap: spacing.sm,
        marginTop: spacing.sm,
        padding: spacing.sm,
    },
    deliveryPointCopy: {
        gap: 4,
    },
    deliveryPointEyebrow: {
        color: colors.mutedText,
        fontSize: 11,
        fontWeight: "700",
        letterSpacing: 0.4,
        textTransform: "uppercase",
    },
    deliveryPointTitle: {
        color: colors.text,
        fontSize: 15,
        fontWeight: "800",
    },
    deliveryPointAddress: {
        color: colors.text,
        fontSize: 13,
        lineHeight: 19,
    },
    deliveryPointMeta: {
        color: colors.mutedText,
        fontSize: 12,
        lineHeight: 17,
    },
    deliveryPointButton: {
        alignItems: "center",
        alignSelf: "flex-start",
        backgroundColor: colors.primary,
        borderRadius: 12,
        justifyContent: "center",
        minHeight: 38,
        paddingHorizontal: spacing.md,
    },
    deliveryPointButtonText: {
        color: colors.onPrimary,
        fontSize: 13,
        fontWeight: "700",
    },
    summaryWarning: {
        color: colors.warning,
        fontSize: 13,
        fontWeight: "600",
        lineHeight: 18,
    },
    itemsList: {
        gap: spacing.sm,
        paddingHorizontal: spacing.lg,
    },
    itemsSection: {
        gap: 0,
    },
    itemsSectionCard: {
        backgroundColor: colors.surface,
        borderRadius: spacing.lg,
        gap: spacing.sm,
        overflow: "hidden",
        paddingHorizontal: 0,
        paddingTop: spacing.sm,
        paddingBottom: spacing.sm,
    },
    itemsSectionCardUnavailable: {
        backgroundColor: colors.surfaceElevated,
    },
    itemsSectionHeader: {
        gap: 4,
        paddingBottom: spacing.xs,
        paddingHorizontal: spacing.lg,
    },
    itemsSectionTitle: {
        color: colors.text,
        fontSize: 16,
        fontWeight: "800",
    },
    itemsSectionDescription: {
        color: colors.mutedText,
        fontSize: 13,
        lineHeight: 18,
    },
    itemCard: {
        alignItems: "flex-start",
        backgroundColor: colors.surface,
        borderRadius: 22,
        flexDirection: "row",
        gap: spacing.xs,
        padding: spacing.sm,
    },
    itemCardUnavailable: {
        backgroundColor: colors.surface,
        opacity: 0.9,
    },
    itemMediaColumn: {
        width: 112,
    },
    itemImageButton: {
        borderRadius: 16,
        overflow: "hidden",
    },
    itemImage: {
        aspectRatio: 0.86,
        backgroundColor: colors.surfaceMuted,
        borderRadius: 16,
        width: "100%",
    },
    itemControlRow: {
        alignItems: "center",
        flexDirection: "row",
        gap: spacing.xs,
        justifyContent: "flex-start",
        marginTop: spacing.xs,
    },
    iconActionButton: {
        alignItems: "center",
        backgroundColor: colors.surfaceElevated,
        borderRadius: 12,
        height: 30,
        justifyContent: "center",
        width: 30,
    },
    itemContent: {
        flex: 1,
        gap: spacing.xs,
        justifyContent: "flex-start",
        minWidth: 0,
    },
    itemDetailsButton: {
        gap: spacing.xs,
    },
    priceStack: {
        gap: 0,
        marginBottom: spacing.xs,
    },
    itemLineTotal: {
        color: colors.text,
        fontSize: 17,
        fontWeight: "800",
        lineHeight: 21,
    },
    itemUnitPrice: {
        color: colors.mutedText,
        fontSize: 12,
        fontWeight: "600",
    },
    itemCopy: {
        gap: 2,
        minWidth: 0,
    },
    itemTitle: {
        color: colors.text,
        fontSize: 15,
        fontWeight: "800",
        lineHeight: 19,
    },
    itemVariant: {
        color: colors.text,
        fontSize: 12,
        fontWeight: "700",
        lineHeight: 16,
    },
    itemSku: {
        color: colors.primary,
        fontSize: 12,
        fontWeight: "700",
    },
    itemAvailability: {
        color: colors.danger,
        fontSize: 12,
        fontWeight: "700",
        marginTop: spacing.xs,
    },
    quantityControl: {
        alignItems: "center",
        backgroundColor: colors.surfaceElevated,
        borderRadius: 12,
        flexDirection: "row",
        height: 30,
        justifyContent: "space-between",
        paddingHorizontal: 3,
        width: 78,
    },
    quantityButton: {
        alignItems: "center",
        height: 20,
        justifyContent: "center",
        width: 20,
    },
    quantityButtonText: {
        color: colors.text,
        fontSize: 16,
        fontWeight: "700",
        lineHeight: 18,
    },
    quantityValue: {
        color: colors.text,
        fontSize: 12,
        fontWeight: "800",
        minWidth: 14,
        textAlign: "center",
    },
    actionDisabled: {
        opacity: 0.45,
    },
    inlineRemoveButton: {
        alignItems: "center",
        backgroundColor: "#FEE2E2",
        borderRadius: 10,
        justifyContent: "center",
        minHeight: 30,
        paddingHorizontal: spacing.sm,
    },
    inlineRemoveButtonText: {
        color: colors.danger,
        fontSize: 12,
        fontWeight: "700",
    },
    pressed: {
        opacity: 0.7,
    },
    swipeAction: {
        alignItems: "center",
        alignSelf: "stretch",
        backgroundColor: colors.favorite,
        borderBottomLeftRadius: 0,
        borderBottomRightRadius: 22,
        borderTopLeftRadius: 0,
        borderTopRightRadius: 22,
        justifyContent: "center",
        marginLeft: 0,
        minWidth: 92,
        paddingHorizontal: spacing.md,
    },
    swipeActionArmed: {
        backgroundColor: "#DC2626",
    },
    swipeActionText: {
        color: "#FFFFFF",
        fontSize: 13,
        fontWeight: "800",
    },
    swipeActionTextArmed: {
        opacity: 0.96,
    },
})
