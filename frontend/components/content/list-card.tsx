import { Image, Pressable, Text, View } from "react-native"
import { useRouter } from "expo-router"
import { Path, Svg } from "react-native-svg"

import { getProductContentSubtitle } from "@/components/content/product-content"
import type { ListCardProps } from "@/components/content/list-card.types"
import { createContentStyles } from "@/components/content/content.styles"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { getProductRoute } from "@/constants/routes"
import { useCopyableProfileValue } from "@/hooks/profile/use-copyable-profile-value"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"

const STAR_PATH = "M12 2.5L14.86 8.28L21.24 9.21L16.62 13.71L17.71 20.07L12 17.07L6.29 20.07L7.38 13.71L2.76 9.21L9.14 8.28L12 2.5Z"

export function ListCard({ product, action, eyebrow }: ListCardProps) {
    const contentStyles = useThemeStyles(createContentStyles)
    const router = useRouter()
    const { t } = useLanguage()
    const { accentPalette } = useTheme()
    const { handleCopy } = useCopyableProfileValue({ t })
    const subtitle = getProductContentSubtitle(product)

    return (
        <View style={contentStyles.listCard}>
            <Pressable
                accessibilityLabel={product.name}
                accessibilityRole="button"
                onPress={() => router.push(getProductRoute(product.id))}
                style={({ pressed }) => [
                    contentStyles.listCardMain,
                    pressed && contentStyles.listCardPressed,
                ]}
            >
                <Image
                    source={{ uri: product.image_url }}
                    style={contentStyles.listCardImage}
                    resizeMode="cover"
                />

                <View style={contentStyles.listCardContent}>
                    {eyebrow ? (
                        <Text style={contentStyles.listCardEyebrow}>{eyebrow}</Text>
                    ) : null}
                    <Text numberOfLines={2} style={contentStyles.listCardTitle}>
                        {product.name}
                    </Text>
                    {product.rating_count > 0 ? (
                        <View style={contentStyles.listCardRatingRow}>
                            <Svg width={12} height={12} viewBox="0 0 24 24">
                                <Path d={STAR_PATH} fill="#FFC83D" />
                            </Svg>
                            <Text style={contentStyles.listCardRatingValue}>{product.rating_avg.toFixed(1)}</Text>
                            <Text style={contentStyles.listCardRatingCount}>({product.rating_count})</Text>
                        </View>
                    ) : null}
                    {subtitle ? (
                        <Text numberOfLines={2} style={contentStyles.listCardSubtitle}>
                            {subtitle}
                        </Text>
                    ) : null}
                </View>
            </Pressable>

            {product.sku ? (
                <Pressable
                    accessibilityLabel={product.sku}
                    accessibilityRole="button"
                    onPress={() => {
                        void handleCopy(product.sku)
                    }}
                    style={({ pressed }) => pressed && contentStyles.listCardMetaPressed}
                >
                    <Text numberOfLines={1} style={[contentStyles.listCardMeta, { color: accentPalette.primary }]}>
                        {product.sku}
                    </Text>
                </Pressable>
            ) : null}

            {action ? <View style={contentStyles.listCardAction}>{action}</View> : null}
        </View>
    )
}
