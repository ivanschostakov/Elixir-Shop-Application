import { Image, Pressable, Text, View } from "react-native"
import { useRouter } from "expo-router"
import { Path, Svg } from "react-native-svg"

import {
    getProductContentSubtitle,
    getProductPriceDisplay,
    isProductOutOfStock,
} from "@/components/content/product-content"
import { contentStyles } from "@/components/content/content.styles"
import type { ProductCardProps } from "@/components/content/product-card.types"
import { getProductRoute } from "@/constants/routes"
import { useCopyableProfileValue } from "@/hooks/profile/use-copyable-profile-value"
import { useLanguage } from "@/providers/language-provider"

const STAR_PATH = "M12 2.5L14.86 8.28L21.24 9.21L16.62 13.71L17.71 20.07L12 17.07L6.29 20.07L7.38 13.71L2.76 9.21L9.14 8.28L12 2.5Z"

export function ProductCard({ product, style }: ProductCardProps) {
    const router = useRouter()
    const { t } = useLanguage()
    const { handleCopy } = useCopyableProfileValue({ t })
    const subtitle = getProductContentSubtitle(product)
    const priceDisplay = getProductPriceDisplay(product)
    const isOutOfStock = isProductOutOfStock(product)

    return (
        <View style={[contentStyles.productCard, style]}>
            <Pressable
                accessibilityLabel={product.name}
                accessibilityRole="button"
                onPress={() => router.push(getProductRoute(product.id))}
                style={({ pressed }) => [
                    contentStyles.productCardContent,
                    pressed && contentStyles.productCardPressed,
                ]}
            >
                <View style={contentStyles.productImageWrap}>
                    <Image
                        source={{ uri: product.image_url }}
                        style={contentStyles.productImage}
                        resizeMode="cover"
                    />
                    {isOutOfStock ? (
                        <View
                            style={[
                                contentStyles.productImageOutOfStockOverlay,
                                { pointerEvents: "none" },
                            ]}
                        >
                            <View style={contentStyles.productImageOutOfStockBadge}>
                                <Text style={contentStyles.productImageOutOfStockText}>
                                    {t("product.variantOutOfStock")}
                                </Text>
                            </View>
                        </View>
                    ) : null}
                </View>

                <View style={contentStyles.productBody}>
                    <View style={contentStyles.productPriceRow}>
                        {priceDisplay ? (
                            <View style={contentStyles.productPriceBlock}>
                                <Text
                                    numberOfLines={1}
                                    style={[
                                        contentStyles.productPrice,
                                        priceDisplay.hasDiscount && contentStyles.productPriceDiscounted,
                                    ]}
                                >
                                    {`${priceDisplay.prefix}${priceDisplay.currentLabel}`}
                                </Text>
                                {priceDisplay.hasDiscount ? (
                                    <View style={contentStyles.productDiscountMetaRow}>
                                        <Text numberOfLines={1} style={contentStyles.productOriginalPrice}>
                                            {priceDisplay.originalLabel ?? ""}
                                        </Text>
                                        <Text numberOfLines={1} style={contentStyles.productDiscountPercent}>
                                            {priceDisplay.discountLabel ?? ""}
                                        </Text>
                                    </View>
                                ) : null}
                            </View>
                        ) : null}
                        {product.rating_count > 0 ? (
                            <View style={contentStyles.productRatingRow}>
                                <Svg width={12} height={12} viewBox="0 0 24 24">
                                    <Path d={STAR_PATH} fill="#FFC83D" />
                                </Svg>
                                <Text style={contentStyles.productRatingValue}>{product.rating_avg.toFixed(1)}</Text>
                                <Text style={contentStyles.productRatingCount}>({product.rating_count})</Text>
                            </View>
                        ) : null}
                    </View>
                    <Text numberOfLines={1} style={contentStyles.productTitle}>
                        {product.name}
                    </Text>
                    {subtitle ? (
                        <Text numberOfLines={1} style={contentStyles.productSubtitle}>
                            {subtitle}
                        </Text>
                    ) : null}
                </View>
            </Pressable>

            {product.sku ? (
                <View style={contentStyles.productMetaWrap}>
                    <Pressable
                        accessibilityLabel={product.sku}
                        accessibilityRole="button"
                        onPress={() => {
                            void handleCopy(product.sku)
                        }}
                        style={({ pressed }) => [
                            contentStyles.productMetaBadge,
                            pressed && contentStyles.productMetaBadgePressed,
                        ]}
                    >
                        <Text style={contentStyles.productMetaBadgeText}>{product.sku}</Text>
                    </Pressable>
                </View>
            ) : null}
        </View>
    )
}
