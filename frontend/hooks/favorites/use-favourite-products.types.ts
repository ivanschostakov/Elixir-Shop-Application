import type { ProductRead } from "@/types/product"

export type UseFavouriteProductsResult = {
    products: ProductRead[]
    loading: boolean
    refreshing: boolean
    error: string | null
    refresh: () => Promise<void>
    removeFavourite: (productId: number) => Promise<void>
    removingProductId: number | null
}
