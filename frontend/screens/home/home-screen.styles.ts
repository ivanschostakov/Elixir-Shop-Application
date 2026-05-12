import { StyleSheet } from "react-native"

import { colors } from "@/theme/colors"
import { spacing } from "@/theme/spacing"

export const homeScreenStyles = StyleSheet.create({
    screen: {
        flex: 1,
        backgroundColor: colors.pageBackground,
    },
    content: {
        paddingBottom: spacing.lg,
    },
    topGradientSectionWrap: {
        backgroundColor: colors.surface,
    },
    topGradientSection: {
        borderBottomLeftRadius: 28,
        borderBottomRightRadius: 28,
        marginBottom: 0,
        overflow: "hidden",
    },
    topGradientContent: {
        paddingBottom: spacing.md,
        paddingHorizontal: spacing.md,
    },
    searchInputWrap: {
        alignItems: "center",
        backgroundColor: colors.surface,
        borderRadius: 16,
        flexDirection: "row",
        gap: spacing.sm,
        minHeight: 52,
        paddingHorizontal: spacing.md,
    },
    searchIconWrap: {
        alignItems: "center",
        justifyContent: "center",
    },
    searchInput: {
        color: colors.text,
        flex: 1,
        fontSize: 16,
    },
    searchPreviewRow: {
        gap: spacing.sm,
        paddingTop: spacing.sm,
    },
    searchPreviewCard: {
        backgroundColor: colors.surface,
        borderRadius: 14,
        maxWidth: 170,
        minWidth: 140,
        overflow: "hidden",
        width: 160,
    },
    searchPreviewCardPressed: {
        opacity: 0.92,
    },
    searchPreviewThumb: {
        backgroundColor: colors.surfaceMuted,
        height: 86,
        width: "100%",
    },
    searchPreviewTitle: {
        color: colors.text,
        fontSize: 13,
        fontWeight: "600",
        paddingHorizontal: spacing.sm,
        paddingVertical: spacing.xs + 2,
    },
    promoBanner: {
        backgroundColor: "rgba(255, 255, 255, 0.9)",
        borderRadius: 22,
        overflow: "hidden",
    },
    promoBannerSection: {
        backgroundColor: colors.surface,
        borderBottomLeftRadius: 22,
        borderBottomRightRadius: 22,
        marginBottom: spacing.md,
        overflow: "hidden",
        paddingTop: spacing.md,
    },
    promoBannerPressed: {
        opacity: 0.93,
    },
    promoBannerTap: {
        backgroundColor: colors.surface,
        borderRadius: 22,
        overflow: "hidden",
        width: "100%",
    },
    promoImage: {
        aspectRatio: 16 / 9,
        borderRadius: 22,
        width: "100%",
    },
    ordersBlock: {
        backgroundColor: colors.surface,
        borderRadius: 24,
        marginBottom: spacing.md,
        paddingBottom: spacing.md,
        paddingHorizontal: spacing.md,
        paddingTop: spacing.md,
    },
    ordersHeader: {
        marginBottom: spacing.sm,
    },
    ordersEyebrow: {
        color: colors.stateText,
        fontSize: 12,
        fontWeight: "700",
        textTransform: "uppercase",
    },
    ordersTitle: {
        color: colors.text,
        fontSize: 20,
        fontWeight: "800",
        marginTop: spacing.xs,
    },
    orderLoginCard: {
        alignItems: "center",
        backgroundColor: colors.primaryMuted,
        borderRadius: 16,
        paddingHorizontal: spacing.md,
        paddingVertical: spacing.md,
    },
    orderLoginCardPressed: {
        opacity: 0.92,
    },
    orderLoginCardText: {
        color: colors.primary,
        fontSize: 14,
        fontWeight: "700",
    },
    orderLoadingWrap: {
        alignItems: "center",
        justifyContent: "center",
        minHeight: 80,
    },
    ordersRow: {
        gap: spacing.sm,
    },
    orderCard: {
        backgroundColor: colors.surfaceMuted,
        borderRadius: 18,
        minWidth: 132,
        paddingHorizontal: spacing.md,
        paddingVertical: spacing.md,
        width: 146,
    },
    orderCardPressed: {
        opacity: 0.92,
    },
    orderCardTitle: {
        color: colors.text,
        fontSize: 16,
        fontWeight: "800",
    },
    orderCardMeta: {
        color: colors.stateText,
        fontSize: 13,
        marginTop: spacing.xs,
    },
    orderCardTotal: {
        color: colors.text,
        fontSize: 14,
        fontWeight: "700",
        marginTop: spacing.sm,
    },
    orderEmptyCard: {
        backgroundColor: colors.surfaceMuted,
        borderRadius: 16,
        paddingHorizontal: spacing.md,
        paddingVertical: spacing.md,
    },
    orderEmptyText: {
        color: colors.stateText,
        fontSize: 13,
        lineHeight: 19,
    },
    recommendationsSection: {
        marginBottom: spacing.md,
    },
    quickCatalogInBanner: {
        backgroundColor: colors.surface,
        paddingBottom: spacing.md,
        paddingTop: spacing.sm,
    },
    quickCatalogRow: {
        flexDirection: "row",
        gap: spacing.sm,
    },
    quickCatalogItem: {
        alignItems: "center",
        width: 78,
    },
    quickCatalogItemPressed: {
        opacity: 0.9,
    },
    quickCatalogIcon: {
        alignItems: "center",
        backgroundColor: colors.primary,
        borderRadius: 14,
        justifyContent: "center",
        marginBottom: spacing.xs,
        overflow: "hidden",
        padding: 8,
        height: 52,
        width: 52,
    },
    quickCatalogLabel: {
        color: colors.text,
        fontSize: 11,
        fontWeight: "600",
        lineHeight: 14,
        textAlign: "center",
        width: 76,
    },
})
