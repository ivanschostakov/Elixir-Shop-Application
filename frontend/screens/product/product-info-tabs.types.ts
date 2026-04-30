import type { Animated } from "react-native"

import type { TranslationFn } from "@/providers/language-provider.types"
import type { ProductInfoTabKey } from "@/screens/product/product-screen.types"
import type { ProductReviewRead, ProductWithVariantsRead } from "@/types/product"

export type ProductInfoTabsProps = {
    activeInfoTab: ProductInfoTabKey
    indicatorWidth: Animated.Value
    indicatorX: Animated.Value
    onChangeTab: (tabKey: ProductInfoTabKey) => void
    onCopySku: (sku: string) => Promise<boolean>
    onSubmitReview: (value: number, text: string | null) => Promise<void>
    onTabLayout: (tabKey: ProductInfoTabKey, layout: { width: number; x: number }) => void
    product: ProductWithVariantsRead
    reviewEligibilityLoading: boolean
    reviews: ProductReviewRead[]
    reviewsError: string | null
    reviewsCanSubmit: boolean
    reviewsLoading: boolean
    reviewsSubmitting: boolean
    showIndicator: boolean
    t: TranslationFn
}
