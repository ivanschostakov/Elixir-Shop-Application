import { useEffect, useState } from "react"
import { ActivityIndicator, FlatList, Platform, View, useWindowDimensions } from "react-native"
import { useLocalSearchParams } from "expo-router"

import { EmptyState } from "@/components/content/empty-state"
import { ProductBrowseControls } from "@/components/content/product-browse-controls"
import { ProductCard } from "@/components/content/product-card"
import { CatalogTemplate } from "@/components/templates/catalog-template"
import { STICKERS } from "@/constants/stickers"
import { resolveContentTab } from "@/hooks/navigation/use-content-tabs"
import type { ProductBrowseSort } from "@/hooks/products/product-browse"
import { useInfiniteProductCatalog } from "@/hooks/products/use-infinite-product-catalog"
import { useProductCategories } from "@/hooks/products/use-product-categories"
import { useLanguage } from "@/providers/language-provider"
import { discoverScreenStyles } from "@/screens/discover/discover-screen.styles"
import { colors } from "@/theme/colors"

const discoverBrowseMemory: {
    categoryId: number | null
    sort: ProductBrowseSort
} = {
    categoryId: null,
    sort: "newest",
}

export default function DiscoverScreen() {
    const { t } = useLanguage()
    const { width: windowWidth } = useWindowDimensions()
    const params = useLocalSearchParams<{ tab?: string | string[] }>()
    const isProductsTab = resolveContentTab(params.tab) === "products"
    const isWeb = Platform.OS === "web"
    const isDesktop = isWeb && windowWidth >= 1100
    const isTablet = isWeb && windowWidth >= 760
    const [categoryId, setCategoryId] = useState<number | null>(() => discoverBrowseMemory.categoryId)
    const [sort, setSort] = useState<ProductBrowseSort>(() => discoverBrowseMemory.sort)
    const { categories } = useProductCategories(isProductsTab)
    const {
        products: catalogProducts,
        loading: isLoading,
        loadingMore,
        error: screenError,
        loadMore,
    } = useInfiniteProductCatalog({
        categoryId,
        enabled: isProductsTab,
        sort,
    })
    const displayedProducts = isProductsTab ? catalogProducts : []
    const numColumns = isDesktop ? 3 : 2
    const pagePadding = isDesktop ? 24 : isTablet ? 18 : 12
    const gridGap = isDesktop ? 14 : 10
    const maxContentWidth = isDesktop ? 1180 : isTablet ? 960 : undefined

    useEffect(() => {
        discoverBrowseMemory.categoryId = categoryId
        discoverBrowseMemory.sort = sort
    }, [categoryId, sort])

    useEffect(() => {
        if (
            categoryId !== null &&
            categories.length > 0 &&
            !categories.some((category) => category.id === categoryId)
        ) {
            setCategoryId(null)
        }
    }, [categories, categoryId])

    return (
        <CatalogTemplate style={discoverScreenStyles.screen}>
            <FlatList
                data={displayedProducts}
                keyExtractor={(product) => String(product.id)}
                numColumns={numColumns}
                columnWrapperStyle={[
                    discoverScreenStyles.gridRow,
                    {
                        gap: gridGap,
                        paddingHorizontal: pagePadding,
                    },
                ]}
                contentContainerStyle={[
                    discoverScreenStyles.listContent,
                    {
                        paddingTop: isDesktop ? 20 : 16,
                    },
                ]}
                keyboardShouldPersistTaps="handled"
                style={[
                    discoverScreenStyles.list,
                    maxContentWidth ? { alignSelf: "center", maxWidth: maxContentWidth, width: "100%" } : null,
                ]}
                onEndReached={() => {
                    void loadMore()
                }}
                onEndReachedThreshold={0.6}
                ListHeaderComponent={
                    isProductsTab ? (
                        <View
                            style={[
                                discoverScreenStyles.controlsWrap,
                                { paddingHorizontal: pagePadding },
                            ]}
                        >
                            <ProductBrowseControls
                                categories={categories}
                                categoryId={categoryId}
                                onChangeCategoryId={setCategoryId}
                                onChangeSort={setSort}
                                sort={sort}
                            />
                        </View>
                    ) : (
                        <View style={discoverScreenStyles.introBlock} />
                    )
                }
                ListEmptyComponent={
                    !isProductsTab ? (
                        <EmptyState
                            eyebrow={t("common.articles")}
                            title={t("discover.articlesTitle")}
                            description={t("discover.articlesDescription")}
                        />
                    ) : isLoading ? (
                        <View style={discoverScreenStyles.loaderWrap}>
                            <ActivityIndicator color={colors.primary} />
                        </View>
                    ) : screenError ? (
                        <EmptyState
                            eyebrow={t("discover.errorEyebrow")}
                            title={t("discover.errorTitle")}
                            description={screenError}
                        />
                    ) : (
                        <EmptyState
                            sticker={STICKERS.noProducts}
                            eyebrow={t("discover.latestEyebrow")}
                            title={t("discover.emptyBrowseTitle")}
                            description={t("discover.emptyBrowseDescription")}
                        />
                    )
                }
                ListFooterComponent={
                    !isProductsTab || !loadingMore ? null : (
                        <View style={discoverScreenStyles.footerLoaderWrap}>
                            <ActivityIndicator color={colors.primary} />
                        </View>
                    )
                }
                renderItem={({ item }) => (
                    <View style={[discoverScreenStyles.gridItem, { marginBottom: gridGap }]}>
                        <ProductCard product={item} />
                    </View>
                )}
                showsVerticalScrollIndicator={false}
            />
        </CatalogTemplate>
    )
}
