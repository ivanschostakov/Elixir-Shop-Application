import { useLocalSearchParams } from "expo-router"

import ProductScreen from "@/screens/product/product-screen"
import { CatalogRoute } from "@/components/navigation/route-guard"

export default function ProductRoute() {
    const { id, variantId } = useLocalSearchParams<{ id: string, variantId?: string }>()
    const productId = Number(id)
    const parsedVariantId = variantId ? Number(variantId) : Number.NaN
    const preferredVariantId = Number.isInteger(parsedVariantId) && parsedVariantId > 0 ? parsedVariantId : undefined

    return <CatalogRoute><ProductScreen productId={productId} preferredVariantId={preferredVariantId} /></CatalogRoute>
}
