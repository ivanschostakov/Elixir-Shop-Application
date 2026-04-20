import { StyleSheet } from "react-native"

import { colors } from "@/theme/colors"

export const getHeaderStyles = (topInset: number, windowHeight: number) =>
    StyleSheet.create({
        wrapper: {
            backgroundColor: colors.background,
            paddingHorizontal: 16,
            paddingBottom: 4,
            position: "relative",
            zIndex: 20,
        },
        wrapperOverlay: {
            backgroundColor: "rgba(255, 255, 255, 0.94)",
            left: 0,
            paddingTop: topInset,
            position: "absolute",
            right: 0,
            top: 0,
        },
        content: {
            alignItems: "center",
            flexDirection: "row",
            height: 34,
            gap: 6,
            position: "relative",
            zIndex: 2,
        },
        centerSlot: {
            flex: 1,
            minWidth: 0,
            position: "relative",
        },
        centerSlotContent: {
            width: "100%",
        },
        searchBackdrop: {
            height: windowHeight + topInset + 8,
            left: -16,
            position: "absolute",
            right: -16,
            top: -(topInset + 8),
            zIndex: 1,
        },
        searchBackdropBlur: {
            backgroundColor: "rgba(255, 255, 255, 0.18)",
            flex: 1,
        },
        title: {
            color: "#000000",
            fontSize: 18,
            fontWeight: "700",
            paddingHorizontal: 6,
            textAlign: "center",
            width: "100%",
        },
        searchInputContainer: {
            alignItems: "center",
            backgroundColor: "#f8fbfd",
            borderColor: "#d7e4ee",
            borderRadius: 999,
            borderWidth: 1,
            flexDirection: "row",
            height: 34,
            paddingHorizontal: 12,
            width: "100%",
        },
        searchInputContainerConnected: {
            borderTopLeftRadius: 20,
            borderTopRightRadius: 20,
            borderBottomLeftRadius: 0,
            borderBottomRightRadius: 0,
            borderBottomWidth: 0,
        },
        searchInput: {
            color: "#111827",
            flex: 1,
            fontSize: 16,
            paddingVertical: 0,
        },
        searchResultsCard: {
            backgroundColor: colors.background,
            borderColor: "#d7e4ee",
            borderRadius: 20,
            borderWidth: 1,
            left: 0,
            overflow: "hidden",
            position: "absolute",
            right: 0,
            boxShadow: "0px 10px 20px rgba(12, 54, 81, 0.14)",
            top: 34,
            elevation: 10,
            zIndex: 25,
        },
        searchResultsCardConnected: {
            borderTopLeftRadius: 0,
            borderTopRightRadius: 0,
        },
        searchControlsWrap: {
            borderBottomColor: "#e8eff5",
            borderBottomWidth: 1,
            paddingHorizontal: 12,
            paddingVertical: 12,
        },
        searchResultsScroll: {
            maxHeight: 240,
        },
        searchStateRow: {
            alignItems: "center",
            flexDirection: "row",
            gap: 10,
            minHeight: 64,
            paddingHorizontal: 16,
            paddingVertical: 14,
        },
        searchStateText: {
            color: "#526476",
            flex: 1,
            fontSize: 14,
            lineHeight: 20,
        },
        searchErrorText: {
            color: "#be123c",
        },
        searchResultItem: {
            alignItems: "center",
            flexDirection: "row",
            gap: 12,
            paddingHorizontal: 12,
            paddingVertical: 10,
        },
        searchResultItemPressed: {
            backgroundColor: "#f3f8fb",
        },
        searchResultThumb: {
            backgroundColor: "#eef4fa",
            borderRadius: 12,
            height: 48,
            width: 48,
        },
        searchResultThumbPlaceholder: {
            backgroundColor: "#eef4fa",
        },
        searchResultText: {
            flex: 1,
            gap: 4,
            minWidth: 0,
        },
        searchResultTitle: {
            color: "#111827",
            fontSize: 15,
            fontWeight: "700",
        },
        searchResultSubtitle: {
            color: "#6B7280",
            fontSize: 13,
        },
        searchResultDivider: {
            backgroundColor: "#e8eff5",
            height: 1,
            marginLeft: 72,
        },
        sideButton: {
            alignItems: "center",
            height: 34,
            justifyContent: "center",
            width: 34,
        },
        sideButtonPressed: {
            opacity: 0.5,
        },
        sideSlot: {
            alignItems: "center",
            height: 34,
            justifyContent: "center",
            width: 34,
        },
        rightSlot: {
            alignItems: "center",
            flexDirection: "row",
            gap: 6,
            justifyContent: "center",
            minWidth: 34,
            position: "relative",
        },
        slotCluster: {
            alignItems: "center",
            flexDirection: "row",
            gap: 6,
            justifyContent: "flex-end",
        },
        headerActionButton: {
            alignItems: "center",
            height: 34,
            justifyContent: "center",
            width: 34,
        },
        headerActionButtonDisabled: {
            opacity: 0.45,
        },
        menuButton: {
            alignItems: "center",
            height: 34,
            justifyContent: "center",
            width: 34,
        },
        menuButtonPressed: {
            opacity: 0.5,
        },
        menuIcon: {
            gap: 4,
            width: 18,
        },
        menuLine: {
            backgroundColor: colors.primary,
            borderRadius: 999,
            height: 2,
            width: "100%",
        },
        menuPopup: {
            position: "absolute",
            right: 0,
            top: 38,
            minWidth: 140,
            backgroundColor: colors.background,
            borderRadius: 16,
            paddingHorizontal: 10,
            paddingVertical: 10,
            boxShadow: "0px 8px 18px rgba(12, 54, 81, 0.16)",
            elevation: 8,
            zIndex: 10,
        },
        menuSection: {
            alignItems: "center",
        },
        menuDivider: {
            backgroundColor: "#d7e4ee",
            height: 1,
            marginVertical: 8,
            width: "100%",
        },
        menuAction: {
            alignItems: "center",
            justifyContent: "center",
            minHeight: 36,
            paddingHorizontal: 8,
        },
        menuActionPressed: {
            opacity: 0.5,
        },
        signOutText: {
            color: colors.primary,
            fontSize: 12,
            fontWeight: "700",
        },
    })

export type AppHeaderStyles = ReturnType<typeof getHeaderStyles>
