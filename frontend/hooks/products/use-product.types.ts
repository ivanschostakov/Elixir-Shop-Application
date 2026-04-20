import type { ProductWithVariantsRead } from "@/types/product"

export type UseProductResult = {
    product: ProductWithVariantsRead | null
    loading: boolean
    error: string | null
}
