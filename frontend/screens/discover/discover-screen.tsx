import { useEffect, useMemo, useRef, useState } from "react"
import { ActivityIndicator, FlatList, Platform, View, useWindowDimensions } from "react-native"
import { useLocalSearchParams, useRouter } from "expo-router"

import { EmptyState } from "@/components/content/empty-state"
import { ProductBrowseControls } from "@/components/content/product-browse-controls"
import { ProductCard } from "@/components/content/product-card"
import { CatalogTemplate } from "@/components/templates/catalog-template"
import { ROUTES } from "@/constants/routes"
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

const PHONE_LAYOUT_WIDTH = 680
const TABLET_LAYOUT_WIDTH = 980
const DESKTOP_LAYOUT_WIDTH = 1280
const MAX_GRID_COLUMNS = 5

function getMinimumCardWidth(layoutWidth: number): number {
    if (layoutWidth >= DESKTOP_LAYOUT_WIDTH) {
        return 220
    }

    if (layoutWidth >= TABLET_LAYOUT_WIDTH) {
        return 200
    }

    if (layoutWidth > PHONE_LAYOUT_WIDTH) {
        return 188
    }

    return 152
}

function resolveGridColumnCount(layoutWidth: number, columnGap: number): number {
    const minimumCardWidth = getMinimumCardWidth(layoutWidth)
    const projectedColumns = Math.floor((layoutWidth + columnGap) / (minimumCardWidth + columnGap))
    const maxColumns = layoutWidth <= PHONE_LAYOUT_WIDTH ? 2 : MAX_GRID_COLUMNS

    return Math.max(2, Math.min(maxColumns, projectedColumns))
}

function chunkIntoRows<TItem>(items: TItem[], columns: number): TItem[][] {
    if (!items.length) {
        return []
    }

    const rows: TItem[][] = []
    for (let index = 0; index < items.length; index += columns) {
        rows.push(items.slice(index, index + columns))
    }

    return rows
}

function parseCategoryId(input: string | string[] | undefined): number | null {
    const rawValue = Array.isArray(input) ? input[0] : input
    if (!rawValue) {
        return null
    }

    const parsedValue = Number(rawValue)
    return Number.isInteger(parsedValue) && parsedValue > 0 ? parsedValue : null
}

function parseQuery(input: string | string[] | undefined): string {
    const rawValue = Array.isArray(input) ? input[0] : input
    return (rawValue ?? "").trim()
}

export default function DiscoverScreen() {
    const router = useRouter()
    const { t } = useLanguage()
    const { width: windowWidth } = useWindowDimensions()
    const params = useLocalSearchParams<{ tab?: string | string[]; categoryId?: string | string[]; q?: string | string[] }>()
    const isProductsTab = resolveContentTab(params.tab) === "products"
    const incomingCategoryId = parseCategoryId(params.categoryId)
    const query = parseQuery(params.q)
    const isWeb = Platform.OS === "web"
    const isDesktop = isWeb && windowWidth >= 1100
    const isTablet = isWeb && windowWidth >= 760
    const [listWidth, setListWidth] = useState(0)
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
        query,
        sort,
    })
    const displayedProducts = useMemo(
        () => (isProductsTab ? catalogProducts : []),
        [catalogProducts, isProductsTab],
    )
    const hasSearchQuery = query.length > 0
    const hasNoResults = isProductsTab && !isLoading && !screenError && displayedProducts.length === 0
    const rowGap = isDesktop ? 16 : 12
    const columnGap = rowGap
    const maxContentWidth = isDesktop ? 1180 : isTablet ? 960 : undefined
    const layoutWidth = listWidth > 0 ? listWidth : (maxContentWidth ? Math.min(windowWidth, maxContentWidth) : windowWidth)
    const numColumns = resolveGridColumnCount(layoutWidth, columnGap)
    const productRows = useMemo(
        () => chunkIntoRows(displayedProducts, numColumns),
        [displayedProducts, numColumns],
    )

    useEffect(() => {
        discoverBrowseMemory.categoryId = categoryId
        discoverBrowseMemory.sort = sort
    }, [categoryId, sort])

    useEffect(() => {
        if (incomingCategoryId !== null) {
            setCategoryId(incomingCategoryId)
        }
    }, [incomingCategoryId])

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

    if (hasNoResults) {
        return (
            <CatalogTemplate style={discoverScreenStyles.screen}>
                <View style={discoverScreenStyles.screen}>
                    <View style={discoverScreenStyles.controlsWrap}>
                        <ProductBrowseControls
                            categories={categories}
                            categoryId={categoryId}
                            onChangeCategoryId={setCategoryId}
                            onChangeSort={setSort}
                            sort={sort}
                        />
                    </View>
                    <View style={discoverScreenStyles.emptyContent}>
                        <EmptyState
                            actionVariant={hasSearchQuery ? "link" : undefined}
                            sticker={STICKERS.noProducts}
                            eyebrow={t("discover.latestEyebrow")}
                            title={hasSearchQuery ? t("discover.emptySearchTitle") : t("discover.emptyBrowseTitle")}
                            description={
                                hasSearchQuery
                                    ? t("discover.emptySearchDescription")
                                    : t("discover.emptyBrowseDescription")
                            }
                            actionLabel={hasSearchQuery ? t("discover.clearSearch") : undefined}
                            onPressAction={
                                hasSearchQuery
                                    ? () => {
                                        if (categoryId !== null) {
                                            router.replace({
                                                pathname: ROUTES.discover,
                                                params: { tab: "products", categoryId: String(categoryId) },
                                            })
                                            return
                                        }

                                        router.replace({
                                            pathname: ROUTES.discover,
                                            params: { tab: "products" },
                                        })
                                    }
                                    : undefined
                            }
                            variant="plain"
                        />
                    </View>
                </View>
            </CatalogTemplate>
        )
    }

    return (
        <CatalogTemplate style={discoverScreenStyles.screen}>
            <FlatList
                data={productRows}
                extraData={numColumns}
                keyExtractor={(row, index) => {
                    const firstId = row[0]?.id
                    const lastId = row[row.length - 1]?.id

                    if (firstId === undefined || lastId === undefined) {
                        return `discover-row-${index}`
                    }

                    return `discover-row-${firstId}-${lastId}`
                }}
                contentContainerStyle={discoverScreenStyles.listContent}
                keyboardShouldPersistTaps="handled"
                onLayout={({ nativeEvent }) => {
                    const nextWidth = Math.floor(nativeEvent.layout.width)

                    if (nextWidth <= 0 || nextWidth === listWidth) {
                        return
                    }

                    setListWidth(nextWidth)
                }}
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
                    ) : null
                }
                ListFooterComponent={
                    !isProductsTab || !loadingMore ? null : (
                        <View style={discoverScreenStyles.footerLoaderWrap}>
                            <ActivityIndicator color={colors.primary} />
                        </View>
                    )
                }
                renderItem={({ item, index }) => (
                    <View style={discoverScreenStyles.gridItem}>
                        <View
                            style={[
                                discoverScreenStyles.gridRow,
                                {
                                    columnGap,
                                    marginBottom: index === productRows.length - 1 ? 0 : rowGap,
                                },
                            ]}
                        >
                            {item.map((product) => (
                                <View key={product.id} style={discoverScreenStyles.gridItemColumn}>
                                    <ProductCard product={product} style={discoverScreenStyles.gridItemCard} />
                                </View>
                            ))}
                        </View>
                    </View>
                )}
                showsVerticalScrollIndicator={false}
            />
        </CatalogTemplate>
    )
}
