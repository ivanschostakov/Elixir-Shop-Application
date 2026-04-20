import { Image, Pressable, Text, View } from "react-native"
import { useRouter } from "expo-router"

import { getProductContentSubtitle } from "@/components/content/product-content"
import type { ListCardProps } from "@/components/content/list-card.types"
import { contentStyles } from "@/components/content/content.styles"
import { getProductRoute } from "@/constants/routes"
import { useCopyableProfileValue } from "@/hooks/profile/use-copyable-profile-value"
import { useLanguage } from "@/providers/language-provider"

export function ListCard({ product, action, eyebrow }: ListCardProps) {
    const router = useRouter()
    const { t } = useLanguage()
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
                    <Text numberOfLines={1} style={contentStyles.listCardMeta}>
                        {product.sku}
                    </Text>
                </Pressable>
            ) : null}

            {action ? <View style={contentStyles.listCardAction}>{action}</View> : null}
        </View>
    )
}
