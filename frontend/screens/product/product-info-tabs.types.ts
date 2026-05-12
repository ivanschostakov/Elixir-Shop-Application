import type { TranslationFn } from "@/providers/language-provider.types"
import type { ProductInfoTabKey } from "@/screens/product/product-screen.types"
import type { ProductReviewRead, ProductWithVariantsRead, UploadableReviewAttachment } from "@/types/product"

export type ProductInfoTabsProps = {
    activeInfoTab: ProductInfoTabKey
    onChangeTab: (tabKey: ProductInfoTabKey) => void
    onCopySku: (sku: string) => Promise<boolean>
    onSubmitReview: (value: number, text: string | null, attachments: UploadableReviewAttachment[]) => Promise<void>
    product: ProductWithVariantsRead
    reviewEligibilityLoading: boolean
    reviews: ProductReviewRead[]
    reviewsError: string | null
    reviewsCanSubmit: boolean
    reviewsLoading: boolean
    reviewsSubmitting: boolean
    t: TranslationFn
}
