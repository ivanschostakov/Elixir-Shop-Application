import { useMemo } from "react"
import { useWindowDimensions } from "react-native"

import type { ProductRead } from "@/types/product"
import {
    IMAGE_CAROUSEL_CARD_GAP,
    IMAGE_CAROUSEL_MAX_CARD_WIDTH,
    IMAGE_CAROUSEL_VISIBLE_CARD_COUNT,
} from "./image-carousel.constants"
import { spacing } from "@/theme/spacing"

function getCarouselOffset(index: number, step: number): number {
    return Math.max(index * step, 0)
}

export function useLoopedCarousel(products: ProductRead[]) {
    const { width: windowWidth } = useWindowDimensions()
    const viewportLimit = Math.max(windowWidth - spacing.md * 2, 0)
    const totalGapWidth = IMAGE_CAROUSEL_CARD_GAP * Math.max(IMAGE_CAROUSEL_VISIBLE_CARD_COUNT - 1, 0)
    const maxCardWidth = (viewportLimit - totalGapWidth) / IMAGE_CAROUSEL_VISIBLE_CARD_COUNT
    const cardWidth = Math.max(Math.floor(Math.min(maxCardWidth, IMAGE_CAROUSEL_MAX_CARD_WIDTH)), 1)
    const step = cardWidth + IMAGE_CAROUSEL_CARD_GAP
    const viewportWidth = viewportLimit

    const snapOffsets = useMemo(
        () => products.map((_, index) => getCarouselOffset(index, step)),
        [products, step]
    )

    return {
        cardWidth,
        products,
        snapOffsets,
        viewportWidth,
    }
}
