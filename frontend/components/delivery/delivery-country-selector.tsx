import { useEffect, useRef } from "react"
import { Animated, Easing, Pressable, ScrollView } from "react-native"
import { SafeAreaView } from "react-native-safe-area-context"

import { CountryFlag } from "@/components/country-flag/country-flag"
import { INACTIVE_FLAG_OPACITY } from "@/components/delivery/delivery-country-selector.constants"
import type {
    DeliveryCountriesSelectorProps,
    DeliveryCountryButtonProps,
} from "@/components/delivery/delivery-country-selector.types"
import { createDeliveryScreenStyles } from "@/screens/delivery/delivery-screen.styles"
import { useThemeStyles } from "@/hooks/use-theme-styles"

function DeliveryCountryButton({
    countryCode,
    isActive,
    onPress,
}: DeliveryCountryButtonProps) {
    const deliveryScreenStyles = useThemeStyles(createDeliveryScreenStyles)
    const opacity = useRef(new Animated.Value(isActive ? 1 : INACTIVE_FLAG_OPACITY)).current

    useEffect(() => {
        Animated.timing(opacity, {
            toValue: isActive ? 1 : INACTIVE_FLAG_OPACITY,
            duration: 180,
            easing: Easing.out(Easing.quad),
            useNativeDriver: true,
        }).start()
    }, [isActive, opacity])

    return (
        <Animated.View
            style={[
                deliveryScreenStyles.countryButton,
                { opacity },
            ]}
        >
            <Pressable
                hitSlop={6}
                onPress={() => onPress(countryCode)}
            >
                <CountryFlag code={countryCode} style={deliveryScreenStyles.countryFlag} />
            </Pressable>
        </Animated.View>
    )
}

export default function DeliveryCountriesSelector(props: DeliveryCountriesSelectorProps) {
    const deliveryScreenStyles = useThemeStyles(createDeliveryScreenStyles)
    return (
        <SafeAreaView edges={["top", "left"]} style={deliveryScreenStyles.countryBox}>
            <ScrollView
                bounces={false}
                contentContainerStyle={deliveryScreenStyles.countryScrollContent}
                horizontal
                showsHorizontalScrollIndicator={false}
                style={deliveryScreenStyles.countryScroll}
            >
                {props.countryCodes.map((countryCode) => {
                    return (
                        <DeliveryCountryButton
                            key={countryCode}
                            countryCode={countryCode}
                            isActive={props.value === countryCode}
                            onPress={props.onChange}
                        />
                    )
                })}
            </ScrollView>
        </SafeAreaView>
    )
}
