import { useEffect, useRef, useState } from "react"
import {
    ActivityIndicator,
    Alert,
    Pressable,
    ScrollView,
    Text,
    TextInput,
    View,
} from "react-native"
import { router } from "expo-router"
import Swipeable from "react-native-gesture-handler/Swipeable"

import { CountryFlag } from "@/components/country-flag/country-flag"
import { COUNTRY_SELECTOR_CODES } from "@/components/country-flag/country-flag.consts"
import { formatProductPrice } from "@/components/content/product-content"
import { EmptyState } from "@/components/content/empty-state"
import { getProductRoute, ROUTES } from "@/constants/routes"
import { STICKERS } from "@/constants/stickers"
import { useBasket } from "@/hooks/basket/use-basket"
import { useBasketMutations } from "@/hooks/basket/use-basket-mutations"
import {
    setSelectedDeliveryAddress,
} from "@/hooks/delivery/delivery-address-selection-store"
import { useDeliveryCountryPickerFocusRequest } from "@/hooks/delivery/delivery-country-picker-focus-store"
import {
    setSelectedDeliveryCountry,
    useSelectedDeliveryCountry,
} from "@/hooks/delivery/delivery-country-selection-store"
import {
    setSelectedDeliveryPoint,
} from "@/hooks/delivery/delivery-point-selection-store"
import { useLanguage } from "@/providers/language-provider"
import { CartBasketItem } from "@/screens/cart/cart-basket-item"
import { cartScreenStyles } from "@/screens/cart/cart-screen.styles"
import { getBasketErrorMessage } from "@/screens/cart/cart-screen.utils"
import type { DeliveryCountryCode } from "@/services/api/delivery.types"
import type { BasketItemRead } from "@/types/basket"

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

export default function CartScreen() {
    const { t } = useLanguage()
    const { basket, error: basketLoadError, loading, reload } = useBasket()
    const { error: basketActionError, removeItem, updateItemQuantity, updating } = useBasketMutations()
    const selectedDeliveryCountry = useSelectedDeliveryCountry()
    const deliveryCountryPickerFocusRequest = useDeliveryCountryPickerFocusRequest()
    const [promoCode, setPromoCode] = useState("")
    const cartScrollRef = useRef<ScrollView | null>(null)
    const swipeableRefs = useRef<Record<number, Swipeable | null>>({})

    useEffect(() => {
        if (selectedDeliveryCountry || deliveryCountryPickerFocusRequest === 0) {
            return
        }

        cartScrollRef.current?.scrollTo({
            animated: true,
            y: 0,
        })
    }, [deliveryCountryPickerFocusRequest, selectedDeliveryCountry])

    const handleSelectDeliveryCountry = (countryCode: DeliveryCountryCode) => {
        if (selectedDeliveryCountry === countryCode) {
            return
        }

        setSelectedDeliveryCountry(countryCode)
        setSelectedDeliveryAddress(null)
        setSelectedDeliveryPoint(null)
    }

    const handleRemoveItem = async (itemId: number) => {
        try {
            swipeableRefs.current[itemId]?.close()
            await removeItem(itemId)
        } catch (error) {
            Alert.alert(getBasketErrorMessage(error, basketActionError, t))
        }
    }

    const handleConfirmRemoveItem = (itemId: number) => {
        Alert.alert(t("cart.removeConfirmTitle"), t("cart.removeConfirmMessage"), [
            {
                text: t("common.cancel"),
                style: "cancel",
            },
            {
                text: t("cart.removeItem"),
                style: "destructive",
                onPress: () => {
                    void handleRemoveItem(itemId)
                },
            },
        ])
    }

    const handleQuantityDecrease = async (item: BasketItemRead) => {
        if (item.quantity <= 1) {
            handleConfirmRemoveItem(item.id)
            return
        }

        try {
            await updateItemQuantity(item.id, item.quantity - 1)
        } catch (error) {
            Alert.alert(getBasketErrorMessage(error, basketActionError, t))
        }
    }

    const handleQuantityIncrease = async (item: BasketItemRead) => {
        if (item.quantity >= item.available_quantity) {
            return
        }

        try {
            await updateItemQuantity(item.id, item.quantity + 1)
        } catch (error) {
            Alert.alert(getBasketErrorMessage(error, basketActionError, t))
        }
    }

    const handleOpenProduct = (productId: number) => {
        router.push(getProductRoute(productId))
    }

    if (loading && !basket) {
        return (
            <View style={cartScreenStyles.loadingContainer}>
                <ActivityIndicator />
            </View>
        )
    }

    if (basketLoadError && !basket) {
        return (
            <View style={cartScreenStyles.errorContainer}>
                <Text style={cartScreenStyles.errorTitle}>{t("cart.loadFailedTitle")}</Text>
                <Text style={cartScreenStyles.errorText}>{t("cart.loadFailedMessage")}</Text>
                <Pressable
                    accessibilityLabel={t("cart.retry")}
                    accessibilityRole="button"
                    onPress={() => {
                        void reload()
                    }}
                    style={({ pressed }) => [
                        cartScreenStyles.retryButton,
                        pressed && cartScreenStyles.pressed,
                    ]}
                >
                    <Text style={cartScreenStyles.retryButtonText}>{t("cart.retry")}</Text>
                </Pressable>
            </View>
        )
    }

    if (!basket || basket.items.length === 0) {
        return (
            <View style={cartScreenStyles.container}>
                <View style={cartScreenStyles.emptyContent}>
                    <EmptyState
                        sticker={STICKERS.cartEmpty}
                        eyebrow={t("cart.emptyEyebrow")}
                        title={t("cart.emptyTitle")}
                        description={t("cart.emptyDescription")}
                        actionLabel={t("cart.primaryCta")}
                        onPressAction={() => router.push(ROUTES.discover)}
                    />
                </View>
            </View>
        )
    }

    const totalAmountLabel = formatProductPrice(basket.total_amount)
    const availableItems = basket.items.filter((item) => item.is_available)
    const unavailableItems = basket.items.filter((item) => !item.is_available)

    return (
        <View style={cartScreenStyles.container}>
            <ScrollView
                ref={cartScrollRef}
                contentContainerStyle={cartScreenStyles.scrollContent}
                showsVerticalScrollIndicator={false}
            >
                <View style={cartScreenStyles.summaryCard}>
                    <ScrollView
                        bounces={false}
                        contentContainerStyle={cartScreenStyles.deliveryCountryCarouselContent}
                        horizontal
                        showsHorizontalScrollIndicator={false}
                        style={cartScreenStyles.deliveryCountryCarousel}
                    >
                        {COUNTRY_SELECTOR_CODES.map((countryCode) => {
                            const isActive = selectedDeliveryCountry === countryCode

                            return (
                                <Pressable
                                    key={countryCode}
                                    accessibilityLabel={DELIVERY_COUNTRY_NAMES[countryCode]}
                                    accessibilityRole="button"
                                    onPress={() => {
                                        handleSelectDeliveryCountry(countryCode)
                                    }}
                                    style={({ pressed }) => [
                                        cartScreenStyles.deliveryCountryButton,
                                        !isActive && cartScreenStyles.deliveryCountryButtonInactive,
                                        pressed && cartScreenStyles.deliveryCountryButtonPressed,
                                    ]}
                                >
                                    <CountryFlag
                                        code={countryCode}
                                        style={cartScreenStyles.deliveryCountryFlag}
                                    />
                                </Pressable>
                            )
                        })}
                    </ScrollView>

                    <TextInput
                        autoCapitalize="characters"
                        autoCorrect={false}
                        onChangeText={setPromoCode}
                        placeholder={t("cart.promoCodePlaceholder")}
                        style={cartScreenStyles.promoInput}
                        value={promoCode}
                    />
                </View>

                <View style={cartScreenStyles.summaryFooter}>
                    <View style={cartScreenStyles.summaryStats}>
                        <View
                            style={[
                                cartScreenStyles.summaryStat,
                                cartScreenStyles.summaryStatStart,
                            ]}
                        >
                            <Text style={cartScreenStyles.summaryStatLabel}>{t("cart.positionsLabel")}</Text>
                            <Text style={cartScreenStyles.summaryStatValue}>{basket.items_count}</Text>
                        </View>

                        <View
                            style={[
                                cartScreenStyles.summaryStat,
                                cartScreenStyles.summaryStatEnd,
                            ]}
                        >
                            <Text style={cartScreenStyles.summaryStatLabel}>{t("cart.totalAmountLabel")}</Text>
                            <Text
                                style={[
                                    cartScreenStyles.summaryStatValue,
                                    cartScreenStyles.summaryStatValuePrice,
                                ]}
                            >
                                {totalAmountLabel ?? "—"}
                            </Text>
                        </View>
                    </View>

                    {basket.has_unavailable_items ? (
                        <Text style={cartScreenStyles.summaryWarning}>{t("cart.unavailableNotice")}</Text>
                    ) : null}
                </View>

                {availableItems.length ? (
                    <View style={cartScreenStyles.itemsSection}>
                        <View style={cartScreenStyles.itemsSectionHeader}>
                            <Text style={cartScreenStyles.itemsSectionTitle}>
                                {t("cart.availableItemsTitle")}
                            </Text>
                        </View>
                        <View style={cartScreenStyles.itemsSectionCard}>
                            <View style={cartScreenStyles.itemsList}>
                                {availableItems.map((item) => (
                                    <CartBasketItem
                                        key={item.id}
                                        item={item}
                                        onConfirmRemove={handleConfirmRemoveItem}
                                        onDecrease={(nextItem) => {
                                            void handleQuantityDecrease(nextItem)
                                        }}
                                        onIncrease={(nextItem) => {
                                            void handleQuantityIncrease(nextItem)
                                        }}
                                        onOpenProduct={handleOpenProduct}
                                        swipeableRef={(instance) => {
                                            swipeableRefs.current[item.id] = instance
                                        }}
                                        updating={updating}
                                    />
                                ))}
                            </View>
                        </View>
                    </View>
                ) : null}

                {unavailableItems.length ? (
                    <View style={cartScreenStyles.itemsSection}>
                        <View style={cartScreenStyles.itemsSectionHeader}>
                            <Text style={cartScreenStyles.itemsSectionTitle}>
                                {t("cart.unavailableItemsTitle")}
                            </Text>
                            <Text style={cartScreenStyles.itemsSectionDescription}>
                                {t("cart.unavailableItemsDescription")}
                            </Text>
                        </View>
                        <View
                            style={[
                                cartScreenStyles.itemsSectionCard,
                                cartScreenStyles.itemsSectionCardUnavailable,
                            ]}
                        >
                            <View style={cartScreenStyles.itemsList}>
                                {unavailableItems.map((item) => (
                                    <CartBasketItem
                                        key={item.id}
                                        item={item}
                                        onConfirmRemove={handleConfirmRemoveItem}
                                        onDecrease={(nextItem) => {
                                            void handleQuantityDecrease(nextItem)
                                        }}
                                        onIncrease={(nextItem) => {
                                            void handleQuantityIncrease(nextItem)
                                        }}
                                        onOpenProduct={handleOpenProduct}
                                        swipeableRef={(instance) => {
                                            swipeableRefs.current[item.id] = instance
                                        }}
                                        updating={updating}
                                    />
                                ))}
                            </View>
                        </View>
                    </View>
                ) : null}
            </ScrollView>
        </View>
    )
}
