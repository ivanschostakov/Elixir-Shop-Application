import { Image, Pressable, ScrollView, Text } from "react-native"
import { useRouter } from "expo-router"

import { getProductRoute } from "@/constants/routes"
import { ImageCarouselStyles } from "./image-carousel.styles"
import { useLoopedCarousel } from "./image-carousel.hooks"
import type { ImageCarouselProps } from "./image-carousel.types"

export default function ImageCarousel({ products, edgeInset }: ImageCarouselProps) {
    const router = useRouter()

    const {
        cardWidth,
        snapOffsets,
        products: visibleProducts,
        viewportWidth,
    } = useLoopedCarousel(products, edgeInset)

    return (
        <ScrollView
            horizontal
            style={[ImageCarouselStyles.scrollView, { width: viewportWidth }]}
            contentContainerStyle={ImageCarouselStyles.container}
            showsHorizontalScrollIndicator={false}
            scrollEventThrottle={16}
            decelerationRate="fast"
            disableIntervalMomentum
            snapToOffsets={snapOffsets}
        >
            {visibleProducts.map((product) => (
                <Pressable
                    key={product.id}
                    style={[ImageCarouselStyles.item, { width: cardWidth }]}
                    onPress={() => router.push(getProductRoute(product.id))}
                >
                    <Image
                        source={{ uri: product.image_url }}
                        style={ImageCarouselStyles.image}
                        resizeMode="cover"
                    />
                    <Text style={ImageCarouselStyles.title} numberOfLines={2}>
                        {product.name}
                    </Text>
                </Pressable>
            ))}
        </ScrollView>
    )
}
