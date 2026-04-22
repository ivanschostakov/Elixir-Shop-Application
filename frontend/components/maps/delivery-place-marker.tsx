import { useEffect, useRef } from "react"
import { Animated, Easing, Text, View } from "react-native"
import { Path, Svg } from "react-native-svg"

import {
    DELIVERY_PLACE_MARKER_HEIGHT,
    DELIVERY_PLACE_MARKER_INNER_COLOR,
    DELIVERY_PLACE_MARKER_INNER_PATH,
    DELIVERY_PLACE_MARKER_OUTER_COLOR,
    DELIVERY_PLACE_MARKER_OUTER_PATH,
    DELIVERY_PLACE_MARKER_VIEWBOX,
    DELIVERY_PLACE_MARKER_WIDTH,
} from "@/components/maps/delivery-place-marker.constants"
import { deliveryPlaceMarkerStyles as styles } from "@/components/maps/delivery-place-marker.styles"
import type { DeliveryPlaceMarkerProps } from "@/components/maps/delivery-place-marker.types"

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
