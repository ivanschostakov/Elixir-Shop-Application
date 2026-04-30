import type { ProductReviewRead } from "@/types/product"
import type { Dispatch, SetStateAction } from "react"

export type UseProductReviewsResult = {
    reviews: ProductReviewRead[]
    loading: boolean
    error: string | null
    reload: () => Promise<ProductReviewRead[] | null>
    setReviews: Dispatch<SetStateAction<ProductReviewRead[]>>
}
