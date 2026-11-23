import type { ProductBrowseSort } from "@/hooks/products/product-browse"
import type { ProductCategory } from "@/types/product-category"

export type ProductBrowseControlsProps = {
    categories: ProductCategory[]
    categoryId: number | null
    newOnly: boolean
    onChangeCategoryId: (categoryId: number | null) => void
    onChangeNewOnly: (newOnly: boolean) => void
    onChangeSort: (sort: ProductBrowseSort) => void
    sort: ProductBrowseSort
}

export type CategorySelectionValue = number | "all" | "new"

export type { AppPickerOption as PickerOption } from "@/components/platform/app-picker"
