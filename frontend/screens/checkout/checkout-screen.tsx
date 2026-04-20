import { Pressable, ScrollView, Text, View } from "react-native"
import { router } from "expo-router"

import { ROUTES } from "@/constants/routes"
import {
    useSelectedDeliveryAddress,
} from "@/hooks/delivery/delivery-address-selection-store"
import {
    useSelectedDeliveryCountry,
} from "@/hooks/delivery/delivery-country-selection-store"
import {
    useSelectedDeliveryPoint,
} from "@/hooks/delivery/delivery-point-selection-store"
import { useLanguage } from "@/providers/language-provider"
import { checkoutScreenStyles } from "@/screens/checkout/checkout-screen.styles"
import type { CdekDeliveryCalculation, DeliveryCountryCode } from "@/services/api/delivery.types"

const DELIVERY_COUNTRY_NAMES: Record<DeliveryCountryCode, string> = {
    AE: "ОАЭ",
    AM: "Армения",
    AZ: "Азербайджан",
    BD: "Бангладеш",
    BY: "Беларусь",
    CN: "Китай",
    GE: "Грузия",
    ID: "Индонезия",
    IL: "Израиль",
    IN: "Индия",
    JP: "Япония",
    KG: "Киргизия",
    KZ: "Казахстан",
    MD: "Молдова",
    MN: "Монголия",
    RS: "Сербия",
    RU: "Россия",
    TH: "Таиланд",
    US: "США",
    UZ: "Узбекистан",
    VN: "Вьетнам",
}

function formatMoney(amount?: number | null, currency?: string | null) {
    if (amount === null || amount === undefined) {
        return null
    }

    if (currency) {
        try {
            return new Intl.NumberFormat("ru-RU", {
                style: "currency",
                currency,
                maximumFractionDigits: Number.isInteger(amount) ? 0 : 2,
            }).format(amount)
        } catch {
            return `${amount.toFixed(2)} ${currency}`
        }
    }

    return amount.toFixed(2)
}

function getDayDeclension(days: number) {
    const mod10 = days % 10
    const mod100 = days % 100

    if (mod10 === 1 && mod100 !== 11) {
        return "день"
    }

    if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) {
        return "дня"
    }

    return "дней"
}

function formatDeliveryPeriod(deliveryCalculation?: CdekDeliveryCalculation | null) {
    if (!deliveryCalculation) {
        return null
    }

    if (deliveryCalculation.period_min === deliveryCalculation.period_max) {
        return `${deliveryCalculation.period_min} ${getDayDeclension(deliveryCalculation.period_min)}`
    }

    return `${deliveryCalculation.period_min}-${deliveryCalculation.period_max} ${getDayDeclension(deliveryCalculation.period_max)}`
}

export default function CheckoutScreen() {
    const { t } = useLanguage()
    const selectedDeliveryCountry = useSelectedDeliveryCountry()
    const selectedDeliveryPoint = useSelectedDeliveryPoint()
    const selectedDeliveryAddress = useSelectedDeliveryAddress()

    const selectedCountryName = selectedDeliveryCountry
        ? DELIVERY_COUNTRY_NAMES[selectedDeliveryCountry]
        : null
    const selectedProvider = selectedDeliveryPoint?.provider ?? selectedDeliveryAddress?.provider ?? null
    const selectedCalculation =
        selectedDeliveryPoint?.deliveryCalculation
        ?? selectedDeliveryAddress?.deliveryCalculation
        ?? null
    const deliveryCost = formatMoney(selectedCalculation?.delivery_sum, selectedCalculation?.currency)
    const deliveryPeriod = formatDeliveryPeriod(selectedCalculation)
    const hasSelection = Boolean(selectedDeliveryPoint || selectedDeliveryAddress)

    return (
        <ScrollView
            contentContainerStyle={checkoutScreenStyles.content}
            style={checkoutScreenStyles.container}
        >
            <View style={checkoutScreenStyles.heroCard}>
                <Text style={checkoutScreenStyles.eyebrow}>
                    {t("route.checkout")}
                </Text>
                <Text style={checkoutScreenStyles.title}>
                    {t("checkout.title")}
                </Text>
                <Text style={checkoutScreenStyles.subtitle}>
                    {t("checkout.subtitle")}
                </Text>
            </View>

            <View style={checkoutScreenStyles.summaryCard}>
                <Text style={checkoutScreenStyles.sectionTitle}>
                    {hasSelection ? t("route.delivery") : t("checkout.noDeliveryTitle")}
                </Text>

                {hasSelection ? (
                    <View style={checkoutScreenStyles.infoList}>
                        {selectedCountryName ? (
                            <View style={checkoutScreenStyles.infoRow}>
                                <Text style={checkoutScreenStyles.infoLabel}>
                                    {t("checkout.deliveryCountryLabel")}
                                </Text>
                                <Text style={checkoutScreenStyles.infoValue}>
                                    {selectedCountryName}
                                </Text>
                            </View>
                        ) : null}

                        <View style={checkoutScreenStyles.infoRow}>
                            <Text style={checkoutScreenStyles.infoLabel}>
                                {t("checkout.deliveryMethodLabel")}
                            </Text>
                            <Text style={checkoutScreenStyles.infoValue}>
                                {selectedDeliveryPoint
                                    ? t("checkout.deliveryMethodPickup")
                                    : t("checkout.deliveryMethodDoor")}
                            </Text>
                        </View>

                        {selectedProvider ? (
                            <View style={checkoutScreenStyles.infoRow}>
                                <Text style={checkoutScreenStyles.infoLabel}>
                                    {t("checkout.deliveryProviderLabel")}
                                </Text>
                                <Text style={checkoutScreenStyles.infoValue}>
                                    {selectedProvider === "yandex" ? "Яндекс" : "СДЭК"}
                                </Text>
                            </View>
                        ) : null}

                        {selectedDeliveryPoint ? (
                            <>
                                <View style={checkoutScreenStyles.infoRow}>
                                    <Text style={checkoutScreenStyles.infoLabel}>
                                        {t("checkout.deliveryPointLabel")}
                                    </Text>
                                    <Text style={checkoutScreenStyles.infoValue}>
                                        {selectedDeliveryPoint.name}
                                    </Text>
                                </View>
                                <View style={checkoutScreenStyles.infoRow}>
                                    <Text style={checkoutScreenStyles.infoLabel}>
                                        {t("checkout.deliveryAddressLabel")}
                                    </Text>
                                    <Text style={checkoutScreenStyles.infoValue}>
                                        {selectedDeliveryPoint.address_full || selectedDeliveryPoint.address}
                                    </Text>
                                </View>
                                {selectedDeliveryPoint.work_time ? (
                                    <View style={checkoutScreenStyles.infoRow}>
                                        <Text style={checkoutScreenStyles.infoLabel}>
                                            {t("checkout.deliveryNotesLabel")}
                                        </Text>
                                        <Text style={checkoutScreenStyles.infoValue}>
                                            {selectedDeliveryPoint.work_time}
                                        </Text>
                                    </View>
                                ) : null}
                            </>
                        ) : null}

                        {selectedDeliveryAddress ? (
                            <>
                                <View style={checkoutScreenStyles.infoRow}>
                                    <Text style={checkoutScreenStyles.infoLabel}>
                                        {t("checkout.deliveryAddressLabel")}
                                    </Text>
                                    <Text style={checkoutScreenStyles.infoValue}>
                                        {selectedDeliveryAddress.address}
                                    </Text>
                                </View>
                                {selectedDeliveryAddress.subtitle ? (
                                    <View style={checkoutScreenStyles.infoRow}>
                                        <Text style={checkoutScreenStyles.infoLabel}>
                                            {t("checkout.deliveryNotesLabel")}
                                        </Text>
                                        <Text style={checkoutScreenStyles.infoValue}>
                                            {selectedDeliveryAddress.subtitle}
                                        </Text>
                                    </View>
                                ) : null}
                            </>
                        ) : null}

                        {deliveryCost ? (
                            <View style={checkoutScreenStyles.infoRow}>
                                <Text style={checkoutScreenStyles.infoLabel}>
                                    {t("checkout.deliveryCostLabel")}
                                </Text>
                                <Text style={checkoutScreenStyles.infoValue}>
                                    {deliveryCost}
                                </Text>
                            </View>
                        ) : null}

                        {deliveryPeriod ? (
                            <View style={checkoutScreenStyles.infoRow}>
                                <Text style={checkoutScreenStyles.infoLabel}>
                                    {t("checkout.deliveryPeriodLabel")}
                                </Text>
                                <Text style={checkoutScreenStyles.infoValue}>
                                    {deliveryPeriod}
                                </Text>
                            </View>
                        ) : null}
                    </View>
                ) : (
                    <Text style={checkoutScreenStyles.subtitle}>
                        {t("checkout.noDeliveryMessage")}
                    </Text>
                )}

                <View style={checkoutScreenStyles.actionRow}>
                    <Pressable
                        accessibilityLabel={t("checkout.openDelivery")}
                        accessibilityRole="button"
                        onPress={() => {
                            router.push(ROUTES.delivery)
                        }}
                        style={({ pressed }) => [
                            checkoutScreenStyles.secondaryButton,
                            pressed && checkoutScreenStyles.secondaryButtonPressed,
                        ]}
                    >
                        <Text style={checkoutScreenStyles.secondaryButtonText}>
                            {t("checkout.openDelivery")}
                        </Text>
                    </Pressable>

                    <Pressable
                        accessibilityLabel={t("checkout.openBasket")}
                        accessibilityRole="button"
                        onPress={() => {
                            router.push(ROUTES.basket)
                        }}
                        style={({ pressed }) => [
                            checkoutScreenStyles.secondaryButton,
                            pressed && checkoutScreenStyles.secondaryButtonPressed,
                        ]}
                    >
                        <Text style={checkoutScreenStyles.secondaryButtonText}>
                            {t("checkout.openBasket")}
                        </Text>
                    </Pressable>
                </View>
            </View>
        </ScrollView>
    )
}
