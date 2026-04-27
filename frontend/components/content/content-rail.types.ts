import type { ProductWithVariantsRead } from "@/types/product"

export type ContentRailProps = {
    title: string
    eyebrow?: string
    description?: string
    actionLabel?: string
    onPressAction?: () => void
    products: ProductWithVariantsRead[]
    layout?: "carousel" | "grid"
    gridVariant?: "default" | "discover"
    mergeHeaderWithFirstRow?: boolean
    carouselEdgeInset?: number
    loadingMore?: boolean
}
