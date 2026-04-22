import { StyleSheet } from "react-native"

import {
    DELIVERY_PLACE_MARKER_HEIGHT,
    DELIVERY_PLACE_MARKER_LABEL_BACKGROUND,
    DELIVERY_PLACE_MARKER_LABEL_COLOR,
} from "@/components/maps/delivery-place-marker.constants"

export const deliveryPlaceMarkerStyles = StyleSheet.create({
    root: {
        alignItems: "center",
    },
    labelBubble: {
        backgroundColor: DELIVERY_PLACE_MARKER_LABEL_BACKGROUND,
        borderRadius: 999,
        paddingHorizontal: 12,
        paddingVertical: 7,
        position: "absolute",
        bottom: DELIVERY_PLACE_MARKER_HEIGHT + 12,
    },
    labelText: {
        color: DELIVERY_PLACE_MARKER_LABEL_COLOR,
        fontSize: 12,
        fontWeight: "700",
        textAlign: "center",
    },
    markerShadow: {
        shadowColor: "#2D120F",
        shadowOffset: { width: 0, height: 6 },
        shadowOpacity: 0.16,
        shadowRadius: 14,
        elevation: 6,
    },
})
