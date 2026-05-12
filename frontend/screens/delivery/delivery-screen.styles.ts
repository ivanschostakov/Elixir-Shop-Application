import { DELIVERY_SUGGEST_ICON_BADGE_SIZE } from "@/components/delivery/delivery-suggest-icon.constants"
import { Platform, StyleSheet } from "react-native"
import { spacing } from "@/theme/spacing"
import { colors } from "@/theme/colors"

export const deliveryScreenStyles = StyleSheet.create({
    viewport: {
        flex: 1,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: colors.pageBackground,
    },
    mapBox: {
        height: 400,
        width: "100%",
        position: "static",
    },
    mapFallback: {
        ...StyleSheet.absoluteFillObject,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: colors.surfaceMuted,
        paddingHorizontal: spacing.lg,
    },
    mapFallbackText: {
        color: colors.mutedText,
        fontSize: 14,
        fontWeight: "600",
        lineHeight: 20,
        textAlign: "center",
    },
    doorDeliveryMarkerOverlay: {
        ...StyleSheet.absoluteFillObject,
        alignItems: "center",
        justifyContent: "center",
        zIndex: 2,
    },
    loadingCard: {
        minWidth: 160,
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "center",
        paddingHorizontal: spacing.md,
        paddingVertical: spacing.sm,
        borderRadius: spacing.xl,
        backgroundColor: colors.surfaceOverlaySoft,
        borderWidth: 1,
        borderColor: "rgba(17,24,39,0.06)",
        ...Platform.select({
            web: {
                boxShadow: "0 10px 30px rgba(17, 24, 39, 0.08)",
            },
            default: {
                shadowColor: "#111827",
                shadowOffset: { width: 0, height: 8 },
                shadowOpacity: 0.08,
                shadowRadius: 20,
                elevation: 4,
            },
        }),
    },
    loadingText: {
        marginLeft: spacing.sm,
        color: colors.mutedText,
        fontSize: 13,
        fontWeight: "500",
    },
    searchKeyboard: {
        flex: 1,
        justifyContent: "flex-end",
    },
    searchOverlayDismiss: {
        ...StyleSheet.absoluteFillObject,
        zIndex: 5,
    },
    searchMapBlur: {
        ...StyleSheet.absoluteFillObject,
        backgroundColor: colors.veilSoft,
    },
    pickupMarkersLoadingOverlay: {
        ...StyleSheet.absoluteFillObject,
        alignItems: "center",
        justifyContent: "center",
        zIndex: 4,
    },
    pickupMarkersBlur: {
        ...StyleSheet.absoluteFillObject,
        backgroundColor: colors.veilSoft,
    },
    pickupMarkersLoadingCard: {
        zIndex: 1,
    },
    floatingControlsSafeArea: {
        ...StyleSheet.absoluteFillObject,
        zIndex: 10,
    },
    floatingControlsFrame: {
        flex: 1,
        justifyContent: "flex-end",
        paddingHorizontal: spacing.md,
        paddingBottom: spacing.md,
    },
    floatingControlsStack: {
        gap: spacing.sm,
        paddingBottom: 88,
    },
    deliveryModeCard: {
        alignSelf: "center",
        backgroundColor: "rgba(255,255,255,0.95)",
        borderColor: "rgba(17,24,39,0.12)",
        borderRadius: 999,
        borderWidth: 1,
        flexDirection: "row",
        position: "relative",
        padding: 4,
        ...Platform.select({
            web: {
                boxShadow: "0 12px 30px rgba(17, 24, 39, 0.12)",
            },
            default: {
                shadowColor: "#111827",
                shadowOffset: { width: 0, height: 10 },
                shadowOpacity: 0.12,
                shadowRadius: 20,
                elevation: 8,
            },
        }),
    },
    deliveryModeIndicator: {
        backgroundColor: colors.primary,
        borderRadius: 999,
        bottom: 4,
        left: 0,
        position: "absolute",
        top: 4,
    },
    deliveryModeButton: {
        alignItems: "center",
        borderRadius: 999,
        justifyContent: "center",
        minHeight: 40,
        paddingHorizontal: spacing.md,
        zIndex: 1,
    },
    deliveryModeButtonPressed: {
        opacity: 0.8,
    },
    deliveryModeButtonActive: {
        backgroundColor: colors.primary,
    },
    deliveryModeButtonText: {
        color: colors.text,
        fontSize: 13,
        fontWeight: "700",
    },
    deliveryModeButtonTextActive: {
        color: colors.onPrimary,
    },
    doorDeliveryCard: {
        backgroundColor: "rgba(255,255,255,0.95)",
        borderColor: "rgba(17,24,39,0.12)",
        borderRadius: spacing.xl,
        borderWidth: 1,
        gap: spacing.sm,
        padding: spacing.md,
        ...Platform.select({
            web: {
                boxShadow: "0 16px 34px rgba(17, 24, 39, 0.12)",
            },
            default: {
                shadowColor: "#111827",
                shadowOffset: { width: 0, height: 12 },
                shadowOpacity: 0.14,
                shadowRadius: 24,
                elevation: 10,
            },
        }),
    },
    doorDeliveryHeader: {
        gap: 2,
    },
    doorDeliveryEyebrow: {
        color: colors.mutedText,
        fontSize: 11,
        fontWeight: "700",
        letterSpacing: 0.4,
        textTransform: "uppercase",
    },
    doorDeliveryTitle: {
        color: colors.text,
        fontSize: 18,
        fontWeight: "800",
    },
    doorDeliveryAddress: {
        color: colors.text,
        fontSize: 15,
        fontWeight: "700",
        lineHeight: 20,
    },
    doorDeliveryMeta: {
        color: colors.mutedText,
        fontSize: 13,
        lineHeight: 18,
    },
    deliveryInfoList: {
        gap: spacing.xs,
    },
    deliveryInfoRow: {
        backgroundColor: "rgba(17,24,39,0.04)",
        borderRadius: 12,
        gap: 2,
        paddingHorizontal: spacing.sm,
        paddingVertical: spacing.sm,
    },
    deliveryInfoRowPressed: {
        opacity: 0.72,
    },
    deliveryInfoLabel: {
        color: colors.mutedText,
        fontSize: 11,
        fontWeight: "700",
        letterSpacing: 0.3,
        textTransform: "uppercase",
    },
    deliveryInfoValue: {
        color: colors.text,
        fontSize: 14,
        fontWeight: "600",
        lineHeight: 20,
    },
    deliveryLinkButton: {
        alignSelf: "flex-start",
    },
    deliveryLinkButtonPressed: {
        opacity: 0.72,
    },
    deliveryLinkButtonText: {
        color: colors.primary,
        fontSize: 14,
        fontWeight: "700",
    },
    pickupFooterExtension: {
        gap: spacing.sm,
        paddingBottom: spacing.sm,
    },
    pickupFooterExtensionInset: {
        marginHorizontal: spacing.lg,
    },
    pickupFooterPrimaryRowInsetReset: {
        marginHorizontal: -spacing.sm+spacing.xs,
        marginBottom: -spacing.sm+spacing.xs/2,
    },
    pickupFooterHeaderRow: {
        alignItems: "center",
        flexDirection: "row",
        gap: spacing.sm,
    },
    pickupFooterHeaderText: {
        flex: 1,
        minWidth: 0,
    },
    pickupFooterTitle: {
        color: colors.text,
        fontSize: 18,
        fontWeight: "800",
        lineHeight: 22,
        marginTop: spacing.sm,
    },
    pickupFooterTitleButton: {
        alignSelf: "flex-start",
    },
    pickupFooterTitleButtonPressed: {
        opacity: 0.64,
    },
    pickupFooterProviderRow: {
        flexDirection: "row",
        gap: spacing.xs,
    },
    pickupFooterProviderButton: {
        alignItems: "center",
        backgroundColor: "rgba(255,255,255,0.95)",
        borderColor: "rgba(17,17,17,0.14)",
        borderRadius: 20,
        borderWidth: 1,
        justifyContent: "center",
        minHeight: 74,
        minWidth: 74,
        overflow: "hidden",
        paddingHorizontal: spacing.xs,
        paddingVertical: spacing.xs,
    },
    pickupFooterProviderButtonActive: {
        backgroundColor: colors.text,
        borderColor: colors.text,
    },
    pickupFooterProviderButtonDisabled: {
        opacity: 0.64,
    },
    pickupFooterProviderButtonPressed: {
        opacity: 0.8,
    },
    pickupFooterProviderButtonText: {
        color: colors.text,
        fontSize: 12,
        fontWeight: "700",
        lineHeight: 15,
        textAlign: "center",
    },
    pickupFooterProviderButtonTextActive: {
        color: colors.surface,
    },
    pickupFooterProviderButtonImage: {
        height: 58,
        resizeMode: "contain",
        width: 58,
    },
    pickupFooterCloseButton: {
        alignItems: "center",
        backgroundColor: "transparent",
        borderRadius: 999,
        borderWidth: 0,
        height: 30,
        justifyContent: "center",
        width: 30,
    },
    pickupFooterCloseButtonPressed: {
        backgroundColor: "rgba(17,17,17,0.06)",
    },
    pickupFooterStatusRow: {
        alignItems: "center",
        backgroundColor: colors.primary,
        borderRadius: 16,
        borderWidth: 0,
        flexDirection: "row",
        justifyContent: "center",
        minHeight: 56,
        paddingHorizontal: spacing.md,
        paddingVertical: spacing.sm,
    },
    pickupFooterInfoList: {
        gap: spacing.xs,
    },
    pickupFooterInfoRow: {
        backgroundColor: "transparent",
        borderWidth: 0,
        borderRadius: 0,
        gap: 2,
        paddingHorizontal: 0,
        paddingVertical: 2,
    },
    pickupFooterInfoRowPressed: {
        opacity: 0.64,
    },
    pickupFooterInfoValue: {
        color: colors.mutedText,
        fontSize: 14,
        fontWeight: "500",
        lineHeight: 18,
    },
    pickupFooterActionsRow: {
        flexDirection: "row",
        gap: spacing.xs,
    },
    pickupFooterErrorBox: {
        backgroundColor: colors.surface,
        borderColor: colors.text,
        borderRadius: 16,
        borderWidth: 1,
        paddingHorizontal: spacing.sm + 2,
        paddingVertical: spacing.sm,
    },
    pickupFooterErrorText: {
        color: colors.text,
        fontSize: 13,
        fontWeight: "600",
        lineHeight: 18,
    },
    doorDeliveryStatusRow: {
        alignItems: "center",
        flexDirection: "row",
        gap: spacing.sm,
    },
    doorDeliveryButton: {
        alignItems: "center",
        backgroundColor: colors.primary,
        borderRadius: 14,
        justifyContent: "center",
        minHeight: 46,
        paddingHorizontal: spacing.md,

    },
    doorDeliveryButtonPressed: {
        opacity: 0.84,
    },
    doorDeliveryButtonDisabled: {
        opacity: 0.5,
    },
    doorDeliveryButtonText: {
        color: colors.onPrimary,
        fontSize: 14,
        fontWeight: "700",
    },
    bottomSearchPanelDock: {
        bottom: -spacing.xl - spacing.sm,
        left: -spacing.xs,
        position: "absolute",
        right: -spacing.xs,
        zIndex: 2,
    },
    bottomSearchPanelSurface: {
        borderTopLeftRadius: 40,
        borderTopRightRadius: 40,
        minHeight: 82,
        ...Platform.select({
            web: {
                boxShadow: "0 -10px 28px rgba(17, 24, 39, 0.14)",
            },
            default: {
                shadowColor: "#111827",
                shadowOffset: { width: 0, height: -8 },
                shadowOpacity: 0.14,
                shadowRadius: 22,
                elevation: 18,
            },
        }),
    },
    bottomSearchPanelContent: {
        justifyContent: "center",
        paddingBottom: spacing.xs,
        paddingHorizontal: 0,
        paddingTop: spacing.sm,
    },
    floatingControlsRow: {
        alignItems: "flex-end",
        flexDirection: "row",
        gap: spacing.sm,
    },
    topMapControlsDock: {
        alignItems: "center",
        flexDirection: "row",
        gap: spacing.sm,
        left: spacing.md,
        position: "absolute",
        right: spacing.md,
        zIndex: 3,
    },
    topMapCountrySelectorWrap: {
        flex: 1,
        minWidth: 0,
        width: 0,
    },
    topMapCountrySelectorScroll: {
        flexGrow: 0,
        width: "100%",
    },
    topMapCountrySelectorContent: {
        gap: spacing.sm,
        paddingHorizontal: 0,
    },
    countrySelectorDock: {
        left: 0,
        position: "absolute",
        right: 0,
        zIndex: 3,
    },
    countrySelectorScroll: {
        flexGrow: 0,
    },
    countrySelectorContent: {
        gap: spacing.sm,
        paddingHorizontal: spacing.md,
    },
    countrySelectorButton: {
        alignItems: "center",
        justifyContent: "center",
        opacity: 1,
    },
    countrySelectorButtonInactive: {
        opacity: 0.38,
    },
    countrySelectorButtonPressed: {
        opacity: 0.7,
    },
    countrySelectorFlag: {
        height: 32,
        width: 32,
    },
    searchPanelDock: {
        flex: 1,
        minWidth: 0,
        marginBottom: spacing.md,
    },
    searchPanelDockFooter: {
        marginBottom: 0,
    },
    webMapFooterContent: {
        gap: spacing.sm,
        paddingBottom: spacing.sm,
    },
    searchInputWrap: {
        alignSelf: "stretch",
        minWidth: 0,
        marginHorizontal: spacing.md,
    },
    searchInputWrapFooter: {
        marginBottom: 0,
        marginHorizontal: spacing.sm+spacing.xs,
        paddingRight: spacing.md,
    },
    searchField: {
        height: 52,
        flexDirection: "row",
        alignItems: "center",
        borderRadius: 999,
        backgroundColor: colors.background,
        borderWidth: 1,
        borderColor: "rgba(0,0,0,0.08)",
        ...Platform.select({
            web: {
                boxShadow: "0 2px 10px rgba(0, 0, 0, 0.14)",
            },
            default: {
                shadowColor: "#000",
                shadowOffset: { width: 0, height: 2 },
                shadowOpacity: 0.14,
                shadowRadius: 10,
                elevation: 6,
            },
        }),
    },
    searchFieldFooter: {
        backgroundColor: "transparent",
        borderColor: "transparent",
        borderWidth: 0,
        borderRadius: 0,
        minHeight: 44,
        ...Platform.select({
            web: {
                boxShadow: "none",
            },
            default: {
                shadowColor: "#000",
                shadowOffset: { width: 0, height: 0 },
                shadowOpacity: 0,
                shadowRadius: 0,
                elevation: 0,
            },
        }),
    },
    searchInputIcon: {
        width: 42,
        alignItems: "center",
        justifyContent: "center",
    },
    resultsBox: {
        maxHeight: 220,
        marginBottom: spacing.sm,
        backgroundColor: colors.background,
        borderRadius: spacing.xl,
        ...Platform.select({
            web: {
                boxShadow: "0 0 12px rgba(0, 0, 0, 0.12)",
            },
            default: {
                shadowColor: "#000",
                shadowOffset: { width: 0, height: 0 },
                shadowOpacity: 0.12,
                shadowRadius: 12,
                elevation: 8,
            },
        }),
        overflow: "hidden",
    },
    resultRow: {
        minHeight: 52,
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "flex-start",
        paddingHorizontal: 14,
        paddingVertical: 10,
        backgroundColor: colors.background,
    },
    resultRowLast: {
        borderBottomWidth: 0,
    },
    resultIconBadge: {
        width: DELIVERY_SUGGEST_ICON_BADGE_SIZE,
        height: DELIVERY_SUGGEST_ICON_BADGE_SIZE,
        borderRadius: 12,
        alignItems: "center",
        justifyContent: "center",
        marginRight: spacing.sm + 4,
        flexShrink: 0,
    },
    resultTextBlock: {
        flex: 1,
        minWidth: 0,
    },
    resultTitle: {
        color: colors.text,
        fontSize: 14,
        fontWeight: "600",
    },
    resultSubtitle: {
        marginTop: 2,
        color: colors.mutedText,
        fontSize: 12,
    },
    statusRow: {
        minHeight: 52,
        flexDirection: "row",
        alignItems: "center",
        paddingHorizontal: 14,
        paddingVertical: 10,
    },
    statusText: {
        color: colors.mutedText,
        fontSize: 13,
    },
    statusSpinner: {
        marginRight: spacing.sm,
    },
    searchInput: {
        flex: 1,
        height: "100%",
        color: colors.text,
        fontSize: 15,
        paddingHorizontal: 0,

    },
    searchInputCloseButton: {
        alignItems: "center",
        height: "100%",
        justifyContent: "center",
        width: 42,
    },
    searchInputCloseButtonPressed: {
        opacity: 0.5,
    },
    cornerButton: {
        alignItems: "center",
        backgroundColor: "rgba(255,255,255,0.95)",
        borderColor: "rgba(17,24,39,0.13)",
        borderRadius: 999,
        borderWidth: 1,
        height: 52,
        justifyContent: "center",
        width: 52,
        ...Platform.select({
            web: {
                boxShadow: "0 12px 30px rgba(17, 24, 39, 0.16)",
            },
            default: {
                shadowColor: "#111827",
                shadowOffset: { width: 0, height: 10 },
                shadowOpacity: 0.14,
                shadowRadius: 20,
                elevation: 8,
            },
        }),
    },
    cornerButtonPressed: {
        opacity: 0.72,
    },
    cornerButtonActive: {
        backgroundColor: colors.primary,
        borderColor: "rgba(10,132,255,0.22)",
    },
    cornerButtonLabel: {
        color: colors.primary,
        fontSize: 24,
        fontWeight: "700",
        lineHeight: 28,
        marginTop: -1,
    },
    cornerButtonLabelActive: {
        color: colors.background,
    },
    countryBox: {
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        zIndex: 20,
    },
    countryScroll: {
        flexGrow: 0,
    },
    countryScrollContent: {
        paddingTop: spacing.md,
        paddingLeft: spacing.md,
        paddingRight: spacing.sm,
        alignItems: "center",
    },
    countryButton: {
        marginRight: 6,
    },
    countryFlag: {
        width: 36,
        marginHorizontal: spacing.xs,
    },
})
