import { useEffect, useRef } from "react"
import { Animated, Easing, StyleSheet, Text, View } from "react-native"
import { Path, Svg } from "react-native-svg"

import {
    DELIVERY_PLACE_MARKER_HEIGHT,
    DELIVERY_PLACE_MARKER_INNER_COLOR,
    DELIVERY_PLACE_MARKER_INNER_PATH,
    DELIVERY_PLACE_MARKER_LABEL_BACKGROUND,
    DELIVERY_PLACE_MARKER_LABEL_COLOR,
    DELIVERY_PLACE_MARKER_OUTER_COLOR,
    DELIVERY_PLACE_MARKER_OUTER_PATH,
    DELIVERY_PLACE_MARKER_VIEWBOX,
    DELIVERY_PLACE_MARKER_WIDTH,
} from "@/components/maps/delivery-place-marker.constants"

type DeliveryPlaceMarkerProps = {
    isFloating?: boolean
    label?: string
}

export function DeliveryPlaceMarker({ isFloating = false, label }: DeliveryPlaceMarkerProps) {
    const floatTranslateY = useRef(new Animated.Value(0)).current
    const floatAnimationRef = useRef<Animated.CompositeAnimation | null>(null)

    useEffect(() => {
        floatAnimationRef.current?.stop()

        if (isFloating) {
            const animation = Animated.loop(
                Animated.sequence([
                    Animated.timing(floatTranslateY, {
                        duration: 560,
                        easing: Easing.inOut(Easing.sin),
                        toValue: -8,
                        useNativeDriver: true,
                    }),
                    Animated.timing(floatTranslateY, {
                        duration: 560,
                        easing: Easing.inOut(Easing.sin),
                        toValue: 0,
                        useNativeDriver: true,
                    }),
                ]),
            )

            floatAnimationRef.current = animation
            animation.start()
            return () => {
                animation.stop()
            }
        }

        Animated.spring(floatTranslateY, {
            bounciness: 6,
            speed: 14,
            toValue: 0,
            useNativeDriver: true,
        }).start()

        return undefined
    }, [floatTranslateY, isFloating])

    return (
        <Animated.View
            pointerEvents="none"
            style={[
                styles.root,
                {
                    transform: [
                        { translateY: -(DELIVERY_PLACE_MARKER_HEIGHT - 2) / 2 },
                        { translateY: floatTranslateY },
                    ],
                },
            ]}
        >
            {label ? (
                <View style={styles.labelBubble}>
                    <Text style={styles.labelText}>
                        {label}
                    </Text>
                </View>
            ) : null}

            <View style={styles.markerShadow}>
                <Svg
                    width={DELIVERY_PLACE_MARKER_WIDTH}
                    height={DELIVERY_PLACE_MARKER_HEIGHT}
                    viewBox={DELIVERY_PLACE_MARKER_VIEWBOX}
                    fill="none"
                >
                    <Path d={DELIVERY_PLACE_MARKER_OUTER_PATH} fill={DELIVERY_PLACE_MARKER_OUTER_COLOR} />
                    <Path d={DELIVERY_PLACE_MARKER_INNER_PATH} fill={DELIVERY_PLACE_MARKER_INNER_COLOR} />
                </Svg>
            </View>
        </Animated.View>
    )
}

const styles = StyleSheet.create({
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
