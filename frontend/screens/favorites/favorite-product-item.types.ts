import type { ProductRead } from "@/types/product"

export type FavoriteProductItemProps = {
    isRemoving: boolean
    onRemove: (productId: number) => Promise<void>
    product: ProductRead
}
