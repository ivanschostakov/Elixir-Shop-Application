import { useEffect, useRef, useState } from "react"
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
import { trackRecommendationCategoryView } from "@/services/api/recommendations"
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
    const trackedCategoryIdRef = useRef<number | null>(null)
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
    const rowGap = isDesktop ? 16 : 12
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

    useEffect(() => {
        if (
            !isProductsTab ||
            categoryId === null ||
            !categories.some((category) => category.id === categoryId)
        ) {
            trackedCategoryIdRef.current = null
            return
        }

        if (trackedCategoryIdRef.current === categoryId) {
            return
        }

        trackedCategoryIdRef.current = categoryId
        void trackRecommendationCategoryView({ category_id: categoryId }).catch(() => undefined)
    }, [categories, categoryId, isProductsTab])

    if (!isProductsTab) {
        return (
            <CatalogTemplate style={discoverScreenStyles.articleEmptyScreen}>
                <View style={discoverScreenStyles.emptyContent}>
                    <EmptyState
                        sticker={STICKERS.noArticles}
                        eyebrow={t("common.articles")}
                        title={t("discover.articlesTitle")}
                        description={t("discover.articlesDescription")}
                        variant="plain"
                    />
                </View>
            </CatalogTemplate>
        )
    }

    return (
        <CatalogTemplate style={discoverScreenStyles.screen}>
            <FlatList
                data={displayedProducts}
                keyExtractor={(product) => String(product.id)}
                numColumns={numColumns}
                columnWrapperStyle={[
                    discoverScreenStyles.gridRow,
                    { marginBottom: rowGap },
                ]}
                contentContainerStyle={discoverScreenStyles.listContent}
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
                    <View
                        style={discoverScreenStyles.controlsWrap}
                    >
                        <ProductBrowseControls
                            categories={categories}
                            categoryId={categoryId}
                            onChangeCategoryId={setCategoryId}
                            onChangeSort={setSort}
                            sort={sort}
                        />
                    </View>
                }
                ListEmptyComponent={
                    isLoading ? (
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
                    <View style={discoverScreenStyles.gridItem}>
                        <ProductCard product={item} style={discoverScreenStyles.gridItemCard} />
                    </View>
                )}
                showsVerticalScrollIndicator={false}
            />
        </CatalogTemplate>
    )
}
