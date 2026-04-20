import { getProductCategories } from "@/services/api/product-categories"
import { useAsyncData } from "@/hooks/shared/use-async-data"
import type { ProductCategory } from "@/types/product-category"

export function useProductCategories(enabled = true) {
    const { data: categories, error, loading } = useAsyncData<ProductCategory[]>({
        deps: [],
        enabled,
        fetcher: getProductCategories,
        initialData: [],
    })

    return { categories, loading, error }
}
