import { useEffect, useRef } from "react"
import { CountryFlag } from "@/components/country-flag/country-flag"
import { deliveryScreenStyles } from "@/screens/delivery/delivery-screen.styles"
import type { DeliveryCountryCode } from "@/services/api/delivery.types"
import { Animated, Easing, Pressable, ScrollView } from "react-native"
import { SafeAreaView } from "react-native-safe-area-context"

type DeliveryCountriesSelectorProps = {
    countryCodes: readonly DeliveryCountryCode[]
    value: DeliveryCountryCode
    onChange: (countryCode: DeliveryCountryCode) => void
}

const INACTIVE_FLAG_OPACITY = 0.5

type DeliveryCountryButtonProps = {
    countryCode: DeliveryCountryCode
    isActive: boolean
    onPress: (countryCode: DeliveryCountryCode) => void
}

function DeliveryCountryButton({
    countryCode,
    isActive,
    onPress,
}: DeliveryCountryButtonProps) {
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
