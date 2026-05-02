export type ProductScreenProps = {
    productId: number
    preferredVariantId?: number
}

export type ProductInfoTabKey = "overview" | "usage" | "details" | "reviews"

export type ProductInfoTabLayout = {
    width: number
    x: number
}
