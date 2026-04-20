import { useMemo } from "react"

import { PRODUCT_BROWSE_LIMIT } from "@/hooks/products/product-browse"
import { useProductCatalog } from "@/hooks/products/use-product-catalog"

export function usePriorityProducts(minPriority: number = 3) {
    const { products, loading, error } = useProductCatalog({
        limit: PRODUCT_BROWSE_LIMIT,
        minPriority,
    })

    const sortedProducts = useMemo(
        () =>
            [...products].sort((leftProduct, rightProduct) => {
                const priorityDifference = rightProduct.priority - leftProduct.priority

                if (priorityDifference !== 0) return priorityDifference
                return rightProduct.id - leftProduct.id
            }),
        [products]
    )

    return { products: sortedProducts, loading, error }
}
