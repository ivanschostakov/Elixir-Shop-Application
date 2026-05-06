import { useLocalSearchParams } from "expo-router"

import ProductScreen from "@/screens/product/product-screen"

export default function ProductRoute() {
    const { id, variantId } = useLocalSearchParams<{ id: string, variantId?: string }>()
    const productId = Number(id)
    const parsedVariantId = variantId ? Number(variantId) : Number.NaN
    const preferredVariantId = Number.isInteger(parsedVariantId) && parsedVariantId > 0 ? parsedVariantId : undefined

    return <ProductScreen productId={productId} preferredVariantId={preferredVariantId} />
}
