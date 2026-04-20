import type { StyleProp, ViewStyle } from "react-native"

import type { ProductWithVariantsRead } from "@/types/product"

export type ProductCardProps = {
    product: ProductWithVariantsRead
    style?: StyleProp<ViewStyle>
}
