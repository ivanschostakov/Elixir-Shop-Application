import { getProductRoute } from "@/constants/routes"
import type { Href } from "expo-router"

import type { ProductRead } from "./product"

export type ImageLinkItem = {
    id: number | string
    name: string
    imageUrl: string
    href: Href
}

export function mapProductToImageLinkItem(product: ProductRead): ImageLinkItem {
    return {
        id: product.id,
        name: product.name,
        imageUrl: product.image_url,
        href: getProductRoute(product.id),
    }
}
