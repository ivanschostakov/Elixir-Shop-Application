import { Text, View } from "react-native"

import { checkoutMapCardWebStyles } from "@/components/maps/checkout-map-card.web.styles"
import { useLanguage } from "@/providers/language-provider"

export default function CheckoutMapCard() {
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
