import { getProductCategories } from "@/services/api/product-categories"
import { useAsyncData } from "@/hooks/shared/use-async-data"
import { useAuth } from "@/providers/auth-provider"
import type { ProductCategory } from "@/types/product-category"

export function useProductCategories(enabled = true) {
    const { user, isReady } = useAuth()
    const { data: categories, error, loading, reload } = useAsyncData<ProductCategory[]>({
        deps: [user?.id],
        enabled: enabled && isReady,
        resetOnLoad: true,
        fetcher: getProductCategories,
        initialData: [],
    })

    return { categories, loading, error, reload }
}
