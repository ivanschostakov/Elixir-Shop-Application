import type { ProductBrowseSort } from "@/hooks/products/product-browse"
import type { ProductCategory } from "@/types/product-category"

export type ProductBrowseControlsProps = {
    categories: ProductCategory[]
    categoryId: number | null
    onChangeCategoryId: (categoryId: number | null) => void
    onChangeSort: (sort: ProductBrowseSort) => void
    sort: ProductBrowseSort
}

export type CategorySelectionValue = number | "all"

export type PickerOption<TValue extends number | string> = {
    key: string
    label: string
    value: TValue
}

export type PickerSheetFieldProps<TValue extends number | string> = {
    disabled?: boolean
    label: string
    onChange: (value: TValue) => void
    options: readonly PickerOption<TValue>[]
    selectedValue: TValue
    title: string
    valueLabel: string
    wrapStyle?: object
    labelStyle?: object
    triggerStyle?: object
}
