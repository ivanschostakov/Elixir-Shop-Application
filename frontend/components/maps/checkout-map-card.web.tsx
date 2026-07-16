import { Text, View } from "react-native"

import { createCheckoutMapCardWebStyles } from "@/components/maps/checkout-map-card.web.styles"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useLanguage } from "@/providers/language-provider"

export default function CheckoutMapCard() {
    const checkoutMapCardWebStyles = useThemeStyles(createCheckoutMapCardWebStyles)
    const { t } = useLanguage()

    return (
        <View style={checkoutMapCardWebStyles.container}>
            <View style={checkoutMapCardWebStyles.mapFallback}>
                <Text style={checkoutMapCardWebStyles.mapFallbackTitle}>Yandex MapKit</Text>
                <Text style={checkoutMapCardWebStyles.mapFallbackText}>{t("checkout.mapUnavailable")}</Text>
            </View>
        </View>
    )
}
