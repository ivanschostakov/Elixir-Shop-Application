import type { TranslationFn } from "@/providers/language-provider.types"
import type { ProductInfoTabKey } from "@/screens/product/product-screen.types"
import type { ProductWithVariantsRead } from "@/types/product"

export type ProductInfoTabsProps = {
    activeInfoTab: ProductInfoTabKey
    onChangeTab: (tabKey: ProductInfoTabKey) => void
    onCopySku: (sku: string) => Promise<boolean>
    product: ProductWithVariantsRead
    t: TranslationFn
}
