import { View } from "react-native"
import { useMemo } from "react"

import { createContentStyles } from "@/components/content/content.styles"
import type {
    CategorySelectionValue,
    PickerOption,
    ProductBrowseControlsProps,
} from "@/components/content/product-browse-controls.types"
import type { ProductBrowseSort } from "@/hooks/products/product-browse"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useLanguage } from "@/providers/language-provider"
import { AppPickerSheetField } from "@/components/platform/app-picker"

export function ProductBrowseControls({
    categories,
    categoryId,
    newOnly,
    onChangeCategoryId,
    onChangeNewOnly,
    onChangeSort,
    sort,
}: ProductBrowseControlsProps) {
    const contentStyles = useThemeStyles(createContentStyles)
    const { t } = useLanguage()
    const categoryOptions = useMemo<readonly PickerOption<CategorySelectionValue>[]>(
        () => [
            {
                key: "category-all",
                label: t("common.all"),
                value: "all",
            },
            {
                key: "category-new",
                label: t("common.newArrivals"),
                value: "new",
            },
            ...categories.map((category) => ({
                key: `category-${category.id}`,
                label: category.name,
                value: category.id,
            })),
        ],
        [categories, t]
    )
    const sortOptions: readonly PickerOption<ProductBrowseSort>[] = [
        { key: "newest", label: t("common.newest"), value: "newest" },
        { key: "name_asc", label: t("common.alphabetAsc"), value: "name_asc" },
        { key: "name_desc", label: t("common.alphabetDesc"), value: "name_desc" },
        { key: "price_asc", label: t("common.priceAsc"), value: "price_asc" },
        { key: "price_desc", label: t("common.priceDesc"), value: "price_desc" },
    ]
    const selectedCategoryValue: CategorySelectionValue = newOnly ? "new" : categoryId ?? "all"
    const isCategoryPickerEnabled = categoryOptions.length > 1
    const categoryLabel =
        categoryOptions.find((option) => option.value === selectedCategoryValue)?.label ??
        t("common.all")
    const sortLabel = sortOptions.find((option) => option.value === sort)?.label ?? sortOptions[0].label

    return (
        <View style={contentStyles.browseControlsRow}>
            <AppPickerSheetField
                disabled={!isCategoryPickerEnabled}
                label={t("common.category")}
                labelStyle={contentStyles.browseSectionLabel}
                onChange={(value) => {
                    if (value === "new") {
                        onChangeCategoryId(null)
                        onChangeNewOnly(true)
                        return
                    }
                    onChangeNewOnly(false)
                    onChangeCategoryId(value === "all" ? null : value)
                }}
                options={categoryOptions}
                selectedValue={selectedCategoryValue}
                title={t("common.category")}
                valueLabel={categoryLabel}
                wrapStyle={contentStyles.browseSectionCompact}
            />

            <AppPickerSheetField
                label={t("common.sort")}
                labelStyle={[
                    contentStyles.browseSectionLabel,
                    contentStyles.browseSectionLabelEnd,
                ] as unknown as object}
                onChange={onChangeSort}
                options={sortOptions}
                selectedValue={sort}
                title={t("common.sort")}
                triggerStyle={contentStyles.browseTriggerEnd}
                valueLabel={sortLabel}
                wrapStyle={[
                    contentStyles.browseSectionCompact,
                    contentStyles.browseSectionCompactEnd,
                ] as unknown as object}
            />
        </View>
    )
}
