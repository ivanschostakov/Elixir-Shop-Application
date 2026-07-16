import { useEffect, useMemo, useState } from "react"
import { Modal, Pressable, Text, View } from "react-native"
import { Picker } from "@react-native-picker/picker"
import { useSafeAreaInsets } from "react-native-safe-area-context"

import { createContentStyles } from "@/components/content/content.styles"
import type {
    CategorySelectionValue,
    PickerOption,
    PickerSheetFieldProps,
    ProductBrowseControlsProps,
} from "@/components/content/product-browse-controls.types"
import type { ProductBrowseSort } from "@/hooks/products/product-browse"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useLanguage } from "@/providers/language-provider"
import { spacing } from "@/theme/spacing"

function PickerSheetField<TValue extends number | string>({
    disabled = false,
    label,
    onChange,
    options,
    selectedValue,
    title,
    valueLabel,
    wrapStyle,
    labelStyle,
    triggerStyle,
}: PickerSheetFieldProps<TValue>) {
    const contentStyles = useThemeStyles(createContentStyles)
    const { t } = useLanguage()
    const { bottom: bottomInset } = useSafeAreaInsets()
    const [isOpen, setIsOpen] = useState(false)
    const [draftValue, setDraftValue] = useState(selectedValue)

    useEffect(() => {
        if (!isOpen) {
            setDraftValue(selectedValue)
        }
    }, [isOpen, selectedValue])

    return (
        <>
            <View style={wrapStyle}>
                <Text style={labelStyle}>{label}</Text>

                <Pressable
                    accessibilityLabel={label}
                    accessibilityRole="button"
                    disabled={disabled}
                    onPress={() => setIsOpen(true)}
                    style={({ pressed }) => [
                        contentStyles.browseTrigger,
                        !disabled && contentStyles.browseTriggerActive,
                        triggerStyle,
                        pressed && !disabled && contentStyles.browseTriggerPressed,
                    ]}
                >
                    <Text
                        numberOfLines={1}
                        style={[
                            contentStyles.browseTriggerValue,
                            disabled && contentStyles.browseTriggerPlaceholderValue,
                        ]}
                    >
                        {valueLabel}
                    </Text>
                </Pressable>
            </View>

            <Modal
                animationType="fade"
                onRequestClose={() => setIsOpen(false)}
                transparent
                visible={isOpen}
            >
                <View style={contentStyles.browsePickerBackdrop}>
                    <Pressable
                        accessibilityRole="button"
                        onPress={() => setIsOpen(false)}
                        style={contentStyles.browsePickerDismissArea}
                    />

                    <View
                        style={[
                            contentStyles.browsePickerSheet,
                            { paddingBottom: Math.max(spacing.lg, bottomInset + spacing.sm) },
                        ]}
                    >
                        <View style={contentStyles.browsePickerHeader}>
                            <Text style={contentStyles.browsePickerTitle}>{title}</Text>

                            <View style={contentStyles.browsePickerActions}>
                                <Pressable
                                    accessibilityLabel={t("common.cancel")}
                                    accessibilityRole="button"
                                    onPress={() => setIsOpen(false)}
                                    style={({ pressed }) => [
                                        contentStyles.browsePickerAction,
                                        pressed && contentStyles.browsePickerActionPressed,
                                    ]}
                                >
                                    <Text style={contentStyles.browsePickerActionText}>
                                        {t("common.cancel")}
                                    </Text>
                                </Pressable>

                                <Pressable
                                    accessibilityLabel={t("common.done")}
                                    accessibilityRole="button"
                                    onPress={() => {
                                        onChange(draftValue)
                                        setIsOpen(false)
                                    }}
                                    style={({ pressed }) => [
                                        contentStyles.browsePickerPrimaryAction,
                                        pressed && contentStyles.browsePickerActionPressed,
                                    ]}
                                >
                                    <Text style={contentStyles.browsePickerPrimaryActionText}>
                                        {t("common.done")}
                                    </Text>
                                </Pressable>
                            </View>
                        </View>

                        <Picker
                            selectedValue={draftValue}
                            onValueChange={(value) => {
                                setDraftValue(value as TValue)
                            }}
                            style={contentStyles.browsePicker}
                        >
                            {options.map((option) => (
                                <Picker.Item key={option.key} label={option.label} value={option.value} />
                            ))}
                        </Picker>
                    </View>
                </View>
            </Modal>
        </>
    )
}

export function ProductBrowseControls({
    categories,
    categoryId,
    onChangeCategoryId,
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
    const selectedCategoryValue: CategorySelectionValue = categoryId ?? "all"
    const isCategoryPickerEnabled = categoryOptions.length > 1
    const categoryLabel =
        categoryOptions.find((option) => option.value === selectedCategoryValue)?.label ??
        t("common.all")
    const sortLabel = sortOptions.find((option) => option.value === sort)?.label ?? sortOptions[0].label

    return (
        <View style={contentStyles.browseControlsRow}>
            <PickerSheetField
                disabled={!isCategoryPickerEnabled}
                label={t("common.category")}
                labelStyle={contentStyles.browseSectionLabel}
                onChange={(value) => {
                    onChangeCategoryId(value === "all" ? null : value)
                }}
                options={categoryOptions}
                selectedValue={selectedCategoryValue}
                title={t("common.category")}
                valueLabel={categoryLabel}
                wrapStyle={contentStyles.browseSectionCompact}
            />

            <PickerSheetField
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
