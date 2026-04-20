import type { ProductRead } from "@/types/product"

export type ContentRailProps = {
    title: string
    eyebrow?: string
    description?: string
    actionLabel?: string
    onPressAction?: () => void
    products: ProductRead[]
}
