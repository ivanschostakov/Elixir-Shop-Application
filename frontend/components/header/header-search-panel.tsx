import { useEffect } from "react"
import {
    ActivityIndicator,
    Image,
    Pressable,
    ScrollView,
    Text,
    TextInput,
    View,
} from "react-native"
import { useRouter } from "expo-router"

import { getProductContentSubtitle } from "@/components/content/product-content"
import type { HeaderSearchPanelProps } from "@/components/header/header-search-panel.types"
import { getProductRoute, ROUTES } from "@/constants/routes"
import { useProductSearch } from "@/hooks/products/use-product-search"
import { colors } from "@/theme/colors"

export function HeaderSearchPanel({
    onClose,
    pathname,
    styles,
    t,
    visible,
}: HeaderSearchPanelProps) {
    const router = useRouter()
    const { clearSearch, error, loading, products, query, setQuery } = useProductSearch(visible)
    const hasSearchQuery = query.trim().length > 0

    useEffect(() => {
        if (!visible) {
            clearSearch()
        }
    }, [clearSearch, visible])

    if (!visible) {
        return null
    }

    return (
        <>
            <View style={[styles.searchInputContainer, styles.searchInputContainerConnected]}>
                <TextInput
                    autoCapitalize="none"
                    autoCorrect={false}
                    autoFocus
                    onChangeText={setQuery}
                    placeholder={
                        pathname === ROUTES.discover
                            ? t("discover.searchPlaceholder")
                            : t("home.searchInputPlaceholder")
                    }
                    placeholderTextColor={colors.mutedText}
                    returnKeyType="search"
                    style={styles.searchInput}
                    value={query}
                />
                {loading ? <ActivityIndicator color={colors.primary} size="small" /> : null}
            </View>

            <View style={[styles.searchResultsCard, styles.searchResultsCardConnected]}>
                {!hasSearchQuery ? (
                    <View style={styles.searchStateRow}>
                        <Text style={styles.searchStateText}>{t("home.searchEmptyQueryMessage")}</Text>
                    </View>
                ) : loading ? (
                    <View style={styles.searchStateRow}>
                        <Text style={styles.searchStateText}>{t("home.searchLoadingMessage")}</Text>
                    </View>
                ) : error ? (
                    <View style={styles.searchStateRow}>
                        <Text style={[styles.searchStateText, styles.searchErrorText]}>{error}</Text>
                    </View>
                ) : products.length ? (
                    <ScrollView
                        nestedScrollEnabled
                        showsVerticalScrollIndicator={false}
                        style={styles.searchResultsScroll}
                    >
                        {products.map((product, index) => (
                            <View key={product.id}>
                                <Pressable
                                    accessibilityLabel={product.name}
                                    accessibilityRole="button"
                                    onPress={() => {
                                        onClose()
                                        clearSearch()
                                        router.push(getProductRoute(product.id))
                                    }}
                                    style={({ pressed }) => [
                                        styles.searchResultItem,
                                        pressed && styles.searchResultItemPressed,
                                    ]}
                                >
                                    {product.image_url ? (
                                        <Image
                                            source={{ uri: product.image_url }}
                                            style={styles.searchResultThumb}
                                            resizeMode="cover"
                                        />
                                    ) : (
                                        <View
                                            style={[
                                                styles.searchResultThumb,
                                                styles.searchResultThumbPlaceholder,
                                            ]}
                                        />
                                    )}

                                    <View style={styles.searchResultText}>
                                        <Text numberOfLines={1} style={styles.searchResultTitle}>
                                            {product.name}
                                        </Text>
                                        <Text numberOfLines={1} style={styles.searchResultSubtitle}>
                                            {getProductContentSubtitle(product)}
                                        </Text>
                                    </View>
                                </Pressable>

                                {index < products.length - 1 ? (
                                    <View style={styles.searchResultDivider} />
                                ) : null}
                            </View>
                        ))}
                    </ScrollView>
                ) : (
                    <View style={styles.searchStateRow}>
                        <Text style={styles.searchStateText}>{t("home.searchNoResultsMessage")}</Text>
                    </View>
                )}
            </View>
        </>
    )
}
