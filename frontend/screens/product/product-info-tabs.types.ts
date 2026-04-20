import type { Animated } from "react-native"

import type { TranslationFn } from "@/providers/language-provider.types"
import type { ProductInfoTabKey } from "@/screens/product/product-screen.types"
import type { ProductWithVariantsRead } from "@/types/product"

export type ProductInfoTabsProps = {
    activeInfoTab: ProductInfoTabKey
    indicatorWidth: Animated.Value
    indicatorX: Animated.Value
    onChangeTab: (tabKey: ProductInfoTabKey) => void
    onCopySku: (sku: string) => Promise<boolean>
    onTabLayout: (tabKey: ProductInfoTabKey, layout: { width: number; x: number }) => void
    product: ProductWithVariantsRead
    reviewCount: number
    reviewRating: string
    showIndicator: boolean
    t: TranslationFn
}
