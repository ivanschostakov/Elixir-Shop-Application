import { ActivityIndicator, Pressable, ScrollView, Text, TextInput, TouchableOpacity, View } from "react-native"
import { Path, Svg } from "react-native-svg"

import { DeliverySuggestIcon } from "@/components/delivery/delivery-suggest-icon"
import type { DeliverySearchPanelProps } from "@/components/delivery/delivery-search-panel.types"
import {
    getResultSubtitle,
    getResultTitle,
} from "@/components/delivery/delivery-search-panel.utils"
import { CLOSE_ICON_PATH } from "@/components/header/app-header.constants"
import { translate } from "@/i18n/translations"
import { createDeliveryScreenStyles } from "@/screens/delivery/delivery-screen.styles"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useTheme } from "@/providers/theme-provider"

function DeliverySearchFieldIcon() {
    const { palette } = useTheme()
    return (
        <Svg width={18} height={18} viewBox="0 0 18 18" fill="none">
            <Path
                d="M8.1 13.2a5.1 5.1 0 1 0 0-10.2 5.1 5.1 0 0 0 0 10.2ZM11.8 11.8 15 15"
                stroke={palette.mutedText}
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.8}
            />
        </Svg>
    )
}

export function DeliverySearchPanel({
    autoFocus = false,
    error = null,
    isLoading = false,
    onChangeText,
    onClose,
    onFocusChange,
    onSubmitSearch,
    onSelectResult,
    results,
    value,
    variant = "floating",
}: DeliverySearchPanelProps) {
    const deliveryScreenStyles = useThemeStyles(createDeliveryScreenStyles)
    const { palette } = useTheme()
    const shouldShowResults = isLoading || !!error || results.length > 0
    const isFooterVariant = variant === "footer"

    return (
        <View
            style={[
                deliveryScreenStyles.searchInputWrap,
                isFooterVariant && deliveryScreenStyles.searchInputWrapFooter,
            ]}
        >
            {shouldShowResults ? (
                <View style={deliveryScreenStyles.resultsBox}>
                    {isLoading ? (
                        <View style={deliveryScreenStyles.statusRow}>
                            <ActivityIndicator
                                color={palette.primary}
                                size="small"
                                style={deliveryScreenStyles.statusSpinner}
                            />
                            <Text style={deliveryScreenStyles.statusText}>Ищем адрес...</Text>
                        </View>
                    ) : null}

                    {!isLoading && error ? (
                        <View style={deliveryScreenStyles.statusRow}>
                            <Text style={deliveryScreenStyles.statusText}>{error}</Text>
                        </View>
                    ) : null}

                    {!isLoading && !error && results.length > 0 ? (
                        <ScrollView
                            nestedScrollEnabled
                            keyboardShouldPersistTaps="handled"
                            showsVerticalScrollIndicator={false}
                        >
                            {results.map((result, index) => {
                                const title = getResultTitle(result)
                                const subtitle = getResultSubtitle(result)

                                return (
                                    <TouchableOpacity
                                        key={`${result.full_address}-${index}`}
                                        activeOpacity={0.7}
                                        onPress={() => onSelectResult(result)}
                                        style={[
                                            deliveryScreenStyles.resultRow,
                                            index === results.length - 1 &&
                                                deliveryScreenStyles.resultRowLast,
                                        ]}
                                    >
                                        <DeliverySuggestIcon result={result} />

                                        <View style={deliveryScreenStyles.resultTextBlock}>
                                            <Text numberOfLines={1} style={deliveryScreenStyles.resultTitle}>
                                                {title}
                                            </Text>
                                            {subtitle ? (
                                                <Text numberOfLines={1} style={deliveryScreenStyles.resultSubtitle}>
                                                    {subtitle}
                                                </Text>
                                            ) : null}
                                        </View>
                                    </TouchableOpacity>
                                )
                            })}
                        </ScrollView>
                    ) : null}
                </View>
            ) : null}

            <View
                style={[
                    deliveryScreenStyles.searchField,
                    isFooterVariant && deliveryScreenStyles.searchFieldFooter,
                ]}
            >
                <View style={deliveryScreenStyles.searchInputIcon}>
                    <DeliverySearchFieldIcon />
                </View>

                <TextInput
                    autoFocus={autoFocus}
                    value={value}
                    onBlur={() => onFocusChange?.(false)}
                    onChangeText={onChangeText}
                    onFocus={() => onFocusChange?.(true)}
                    onSubmitEditing={() => onSubmitSearch?.()}
                    returnKeyType="search"
                    placeholder="Адрес или пункт выдачи"
                    placeholderTextColor="#999"
                    style={deliveryScreenStyles.searchInput}
                />

                {onClose ? (
                    <Pressable
                        accessibilityLabel={translate("nav.closeSearch")}
                        accessibilityRole="button"
                        hitSlop={8}
                        onPress={onClose}
                        style={({ pressed }) => [
                            deliveryScreenStyles.searchInputCloseButton,
                            pressed && deliveryScreenStyles.searchInputCloseButtonPressed,
                        ]}
                    >
                        <Svg width={18} height={18} viewBox="0 0 24 24" fill="none">
                            <Path d={CLOSE_ICON_PATH} fill={palette.mutedText} />
                        </Svg>
                    </Pressable>
                ) : null}
            </View>
        </View>
    )
}
