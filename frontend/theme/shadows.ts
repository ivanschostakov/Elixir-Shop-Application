import { Platform, type ViewStyle } from "react-native"

function platformShadow(variants: { web: ViewStyle; default: ViewStyle }): ViewStyle {
    return Platform.select(variants)
}

export const shadows = {
    deliveryLoadingCard: platformShadow({
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
    deliveryDeliveryModeCard: platformShadow({
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
    deliveryDoorDeliveryCard: platformShadow({
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
    deliveryBottomSearchPanelSurface: platformShadow({
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
    deliverySearchField: platformShadow({
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
    deliverySearchFieldFooter: platformShadow({
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
    deliveryResultsBox: platformShadow({
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
    deliveryCornerButton: platformShadow({
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
    productImageCard: platformShadow({
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
    productSimilarRailCard: platformShadow({
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
    productVariantCard: platformShadow({
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
    footerFooterBase: platformShadow({
            web: {
                boxShadow: "0 -4px 16px rgba(0, 0, 0, 0.12)",
            },
            default: {
                shadowColor: "#000000",
                shadowOffset: { width: 0, height: -4 },
                shadowOpacity: 0.12,
                shadowRadius: 16,
            },
        }),
}
