import { useCallback, useState } from "react"

import { SEARCH_DEBOUNCE_MS } from "@/hooks/products/use-product-search.constants"
import { useProductCatalog } from "@/hooks/products/use-product-catalog"
import type { UseProductSearchResult } from "@/hooks/products/use-product-search.types"

export function useProductSearch(enabled = true): UseProductSearchResult {
    const [query, setQuery] = useState("")
    const { error, loading, products, reload } = useProductCatalog({
        debounceMs: SEARCH_DEBOUNCE_MS,
        enabled,
        limit: 50,
        query,
        skipEmptyQuery: true,
    })

    const clearSearch = useCallback(() => {
        setQuery("")
    }, [])

    return {
        clearSearch,
        error,
        loading,
        products,
        query,
        reload,
        setQuery,
    }
}
