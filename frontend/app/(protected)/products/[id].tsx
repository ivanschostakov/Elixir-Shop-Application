import { useLocalSearchParams } from "expo-router"

import ProductScreen from "@/screens/product/product-screen"

export default function ProductRoute() {
    const { id } = useLocalSearchParams<{ id: string }>()
    const productId = Number(id)

    return <ProductScreen productId={productId} />
}
