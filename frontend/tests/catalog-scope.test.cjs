const { test } = require("node:test")
const assert = require("node:assert/strict")
const loadTs = require("./load-ts.cjs")

test("catalog hooks wait for authentication and reload when customer identity changes", () => {
    const cases = [
        ["hooks/products/use-product-categories.ts", "useProductCategories", "@/services/api/product-categories"],
        ["hooks/home/use-banners.ts", "useBanners", "@/services/api/banners"],
        ["hooks/products/use-product-catalog.ts", "useProductCatalog", "@/services/api/products"],
        ["hooks/products/use-infinite-product-catalog.ts", "useInfiniteProductCatalog", "@/services/api/products"],
        ["hooks/products/use-product.ts", "useProduct", "@/services/api/products", 1],
        ["hooks/products/use-similar-products.ts", "useSimilarProducts", "@/services/api/products", 1],
    ]
    for (const [file, name, api, argument] of cases) {
        let auth = { isReady: false, user: null }, options
        const capture = value => { options = value; return { data: [], items: [] } }
        const hooks = loadTs(file, {
            "@/providers/auth-provider": { useAuth: () => auth },
            "@/hooks/shared/use-async-data": { useAsyncData: capture },
            "@/hooks/shared/use-paginated-data": { usePaginatedData: capture },
            "@/hooks/products/product-browse": { PRODUCT_DISCOVER_PAGE_SIZE: 20 },
            [api]: {},
        })
        hooks[name](argument)
        assert.equal(options.enabled, false, file)
        auth = { isReady: true, user: { id: 30 } }
        hooks[name](argument)
        assert.equal(options.enabled, true, file)
        assert.equal(options.deps[0], 30, file)
        if (!file.includes("infinite")) assert.equal(options.resetOnLoad, true, file)
        auth = { isReady: true, user: null }
        hooks[name](argument)
        assert.equal(options.deps[0], undefined, file)
        assert.equal(options.enabled, true, file)
    }
})
