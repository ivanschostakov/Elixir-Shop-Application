import { useProductCatalog } from "@/hooks/products/use-product-catalog"

export function useLatestProducts(limit = 12) {
    const { products, loading, error } = useProductCatalog({
        limit,
        sort: "newest",
    })

    return { products, loading, error }
}
