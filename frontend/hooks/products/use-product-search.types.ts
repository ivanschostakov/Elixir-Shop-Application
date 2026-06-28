import type { ProductWithVariantsRead } from "@/types/product"

export type UseProductSearchResult = {
    clearSearch: () => void
    error: string | null
    loading: boolean
    products: ProductWithVariantsRead[]
    query: string
    reload: () => Promise<ProductWithVariantsRead[] | null>
    setQuery: (query: string) => void
}
