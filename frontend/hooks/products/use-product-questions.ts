import { useAsyncData } from "@/hooks/shared/use-async-data"
import type { UseProductQuestionsResult } from "@/hooks/products/use-product-questions.types"
import { getProductQuestions } from "@/services/api/products"

export function useProductQuestions(productId: number): UseProductQuestionsResult {
    const { data, error, loading, reload, setData } = useAsyncData({
        deps: [productId],
        fetcher: async () => {
            if (!productId || !Number.isFinite(productId)) {
                throw new Error("Invalid product id")
            }
            return getProductQuestions(productId)
        },
        initialData: { items: [], total: 0 },
        resetOnLoad: true,
    })

    return {
        questions: data.items,
        total: data.total,
        loading,
        error,
        reload,
        setQuestions: setData,
    }
}
