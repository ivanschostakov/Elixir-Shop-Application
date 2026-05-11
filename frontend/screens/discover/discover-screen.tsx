import { useEffect, useMemo, useRef, useState } from "react"
import { ActivityIndicator, FlatList, Image, Platform, Pressable, ScrollView, Text, TextInput, View, useWindowDimensions } from "react-native"
import { useLocalSearchParams, useRouter } from "expo-router"
import { LinearGradient } from "expo-linear-gradient"
import { Path, Svg } from "react-native-svg"

import { EmptyState } from "@/components/content/empty-state"
import { ProductBrowseControls } from "@/components/content/product-browse-controls"
import { ProductCard } from "@/components/content/product-card"
import { CatalogTemplate } from "@/components/templates/catalog-template"
import { STICKERS } from "@/constants/stickers"
import { ROUTES, getProductRoute } from "@/constants/routes"
import { resolveContentTab } from "@/hooks/navigation/use-content-tabs"
import type { ProductBrowseSort } from "@/hooks/products/product-browse"
import { useInfiniteProductCatalog } from "@/hooks/products/use-infinite-product-catalog"
import { useProductCategories } from "@/hooks/products/use-product-categories"
import { useProductSearch } from "@/hooks/products/use-product-search"
import { useAuth } from "@/providers/auth-provider"
import { useLanguage } from "@/providers/language-provider"
import { trackRecommendationCategoryView } from "@/services/api/recommendations"
import { getOrderDrafts } from "@/services/api/order-drafts"
import type { OrderDraftRead } from "@/services/api/order-drafts.types"
import { discoverScreenStyles } from "@/screens/discover/discover-screen.styles"
import { colors } from "@/theme/colors"
import { spacing } from "@/theme/spacing"
import { formatMoney } from "@/utils/formatting"

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

export default function DiscoverScreen() {
    const router = useRouter()
    const { t } = useLanguage()
    const { isAuthenticated } = useAuth()
    const { width: windowWidth } = useWindowDimensions()
    const params = useLocalSearchParams<{ tab?: string | string[] }>()
    const isProductsTab = resolveContentTab(params.tab) === "products"
    const isWeb = Platform.OS === "web"
    const isDesktop = isWeb && windowWidth >= 1100
    const isTablet = isWeb && windowWidth >= 760
    const [listWidth, setListWidth] = useState(0)
    const [categoryId, setCategoryId] = useState<number | null>(() => discoverBrowseMemory.categoryId)
    const [sort, setSort] = useState<ProductBrowseSort>(() => discoverBrowseMemory.sort)
    const [orderDrafts, setOrderDrafts] = useState<OrderDraftRead[]>([])
    const [isLoadingOrderDrafts, setIsLoadingOrderDrafts] = useState(false)
    const trackedCategoryIdRef = useRef<number | null>(null)
    const { categories } = useProductCategories(isProductsTab)
    const { loading: isSearchLoading, products: searchedProducts, query, setQuery } = useProductSearch(isProductsTab)
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
    const displayedProducts = useMemo(
        () => (isProductsTab ? catalogProducts : []),
        [catalogProducts, isProductsTab],
    )
    const rowGap = isDesktop ? 16 : 12
    const columnGap = rowGap
    const maxContentWidth = isDesktop ? 1180 : isTablet ? 960 : undefined
    const layoutWidth = listWidth > 0 ? listWidth : (maxContentWidth ? Math.min(windowWidth, maxContentWidth) : windowWidth)
    const numColumns = resolveGridColumnCount(layoutWidth, columnGap)
    const productRows = useMemo(
        () => chunkIntoRows(displayedProducts, numColumns),
        [displayedProducts, numColumns],
    )
    const hasSearchQuery = query.trim().length > 0
    const searchPreviewProducts = useMemo(
        () => searchedProducts.slice(0, 4),
        [searchedProducts],
    )
    const quickCatalogActions = useMemo(
        () => [
            { key: "catalog", label: t("discover.latestEyebrow"), route: ROUTES.discover, tint: "#0A84FF" },
            { key: "basket", label: t("route.basket"), route: ROUTES.basket, tint: "#16A34A" },
            { key: "favorites", label: t("route.favorites"), route: ROUTES.favorites, tint: "#EF4444" },
            { key: "profile", label: t("route.profile"), route: ROUTES.profile, tint: "#8B5CF6" },
        ],
        [t],
    )

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

    useEffect(() => {
        if (!isAuthenticated) {
            setOrderDrafts([])
            setIsLoadingOrderDrafts(false)
            return
        }

        let isCancelled = false
        setIsLoadingOrderDrafts(true)

        void getOrderDrafts({ limit: 6 })
            .then((drafts) => {
                if (!isCancelled) {
                    setOrderDrafts(drafts)
                }
            })
            .catch(() => {
                if (!isCancelled) {
                    setOrderDrafts([])
                }
            })
            .finally(() => {
                if (!isCancelled) {
                    setIsLoadingOrderDrafts(false)
                }
            })

        return () => {
            isCancelled = true
        }
    }, [isAuthenticated])

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
                    <View>
                        <LinearGradient
                            colors={["#FF6F93", "#FF88B0", "#FFC96B"]}
                            end={{ x: 1, y: 0.9 }}
                            start={{ x: 0, y: 0 }}
                            style={discoverScreenStyles.heroCard}
                        >
                            <View style={discoverScreenStyles.searchInputWrap}>
                                <View style={discoverScreenStyles.searchIconWrap}>
                                    <Svg width={18} height={18} viewBox="0 0 24 24" fill="none">
                                        <Path
                                            d="M11 4a7 7 0 1 0 4.47 12.39l4.07 4.08 1.42-1.42-4.08-4.07A7 7 0 0 0 11 4Zm0 2a5 5 0 1 1 0 10 5 5 0 0 1 0-10Z"
                                            fill={colors.mutedText}
                                        />
                                    </Svg>
                                </View>
                                <TextInput
                                    autoCapitalize="none"
                                    autoCorrect={false}
                                    onChangeText={setQuery}
                                    placeholder={t("discover.searchPlaceholder")}
                                    placeholderTextColor={colors.mutedText}
                                    returnKeyType="search"
                                    style={discoverScreenStyles.searchInput}
                                    value={query}
                                />
                                {isSearchLoading ? (
                                    <ActivityIndicator color={colors.primary} size="small" />
                                ) : null}
                            </View>

                            {hasSearchQuery && searchPreviewProducts.length ? (
                                <ScrollView
                                    horizontal
                                    contentContainerStyle={discoverScreenStyles.searchPreviewRow}
                                    showsHorizontalScrollIndicator={false}
                                >
                                    {searchPreviewProducts.map((product) => (
                                        <Pressable
                                            key={product.id}
                                            accessibilityLabel={product.name}
                                            accessibilityRole="button"
                                            onPress={() => {
                                                router.push(getProductRoute(product.id))
                                            }}
                                            style={({ pressed }) => [
                                                discoverScreenStyles.searchPreviewCard,
                                                pressed && discoverScreenStyles.searchPreviewCardPressed,
                                            ]}
                                        >
                                            {product.image_url ? (
                                                <Image
                                                    source={{ uri: product.image_url }}
                                                    style={discoverScreenStyles.searchPreviewThumb}
                                                    resizeMode="cover"
                                                />
                                            ) : (
                                                <View style={discoverScreenStyles.searchPreviewThumb} />
                                            )}
                                            <Text numberOfLines={1} style={discoverScreenStyles.searchPreviewTitle}>
                                                {product.name}
                                            </Text>
                                        </Pressable>
                                    ))}
                                </ScrollView>
                            ) : null}

                            <Pressable
                                accessibilityLabel={t("discover.latestTitle")}
                                accessibilityRole="button"
                                onPress={() => {
                                    router.push(ROUTES.favorites)
                                }}
                                style={({ pressed }) => [
                                    discoverScreenStyles.promoBanner,
                                    pressed && discoverScreenStyles.promoBannerPressed,
                                ]}
                            >
                                <Text style={discoverScreenStyles.promoEyebrow}>{t("discover.latestEyebrow")}</Text>
                                <Text style={discoverScreenStyles.promoTitle}>{t("discover.latestTitle")}</Text>
                                <Text numberOfLines={2} style={discoverScreenStyles.promoDescription}>
                                    {t("discover.latestDescription")}
                                </Text>
                                <View style={discoverScreenStyles.promoAction}>
                                    <Text style={discoverScreenStyles.promoActionLabel}>{t("cart.primaryCta")}</Text>
                                </View>
                            </Pressable>
                        </LinearGradient>

                        <View style={discoverScreenStyles.ordersBlock}>
                            <View style={discoverScreenStyles.ordersHeader}>
                                <Text style={discoverScreenStyles.ordersEyebrow}>{t("cart.recentDraftsEyebrow")}</Text>
                                <Text style={discoverScreenStyles.ordersTitle}>{t("cart.recentDraftsTitle")}</Text>
                            </View>

                            {!isAuthenticated ? (
                                <Pressable
                                    accessibilityLabel={t("auth.entry.login")}
                                    accessibilityRole="button"
                                    onPress={() => {
                                        router.push(ROUTES.login)
                                    }}
                                    style={({ pressed }) => [
                                        discoverScreenStyles.orderLoginCard,
                                        pressed && discoverScreenStyles.orderLoginCardPressed,
                                    ]}
                                >
                                    <Text style={discoverScreenStyles.orderLoginCardText}>
                                        {t("cart.openDraftsCta")}
                                    </Text>
                                </Pressable>
                            ) : isLoadingOrderDrafts ? (
                                <View style={discoverScreenStyles.orderLoadingWrap}>
                                    <ActivityIndicator color={colors.primary} />
                                </View>
                            ) : orderDrafts.length ? (
                                <ScrollView
                                    horizontal
                                    contentContainerStyle={discoverScreenStyles.ordersRow}
                                    showsHorizontalScrollIndicator={false}
                                >
                                    {orderDrafts.map((draft) => {
                                        const total = formatMoney(Number(draft.grand_total), draft.currency)
                                        return (
                                            <Pressable
                                                key={draft.id}
                                                accessibilityLabel={`${t("cart.recentDraftsOpenDraft")} ${draft.id}`}
                                                accessibilityRole="button"
                                                onPress={() => {
                                                    router.push(`${ROUTES.checkout}?draftId=${draft.id}`)
                                                }}
                                                style={({ pressed }) => [
                                                    discoverScreenStyles.orderCard,
                                                    pressed && discoverScreenStyles.orderCardPressed,
                                                ]}
                                            >
                                                <Text numberOfLines={1} style={discoverScreenStyles.orderCardTitle}>
                                                    #{draft.id}
                                                </Text>
                                                <Text numberOfLines={1} style={discoverScreenStyles.orderCardMeta}>
                                                    {draft.items_count} {t("cart.positionsLabel")}
                                                </Text>
                                                <Text numberOfLines={1} style={discoverScreenStyles.orderCardTotal}>
                                                    {total ?? "—"}
                                                </Text>
                                            </Pressable>
                                        )
                                    })}
                                </ScrollView>
                            ) : (
                                <View style={discoverScreenStyles.orderEmptyCard}>
                                    <Text style={discoverScreenStyles.orderEmptyText}>
                                        {t("cart.emptyDescriptionWithDrafts")}
                                    </Text>
                                </View>
                            )}
                        </View>

                        <View style={discoverScreenStyles.quickCatalogBlock}>
                            <Text style={discoverScreenStyles.quickCatalogTitle}>{t("discover.latestEyebrow")}</Text>
                            <View style={discoverScreenStyles.quickCatalogRow}>
                                {quickCatalogActions.map((action) => (
                                    <Pressable
                                        key={action.key}
                                        accessibilityLabel={action.label}
                                        accessibilityRole="button"
                                        onPress={() => {
                                            router.push(action.route)
                                        }}
                                        style={({ pressed }) => [
                                            discoverScreenStyles.quickCatalogItem,
                                            pressed && discoverScreenStyles.quickCatalogItemPressed,
                                        ]}
                                    >
                                        <View
                                            style={[
                                                discoverScreenStyles.quickCatalogIcon,
                                                { backgroundColor: action.tint },
                                            ]}
                                        />
                                        <Text numberOfLines={1} style={discoverScreenStyles.quickCatalogLabel}>
                                            {action.label}
                                        </Text>
                                    </Pressable>
                                ))}
                            </View>
                        </View>

                        <View style={discoverScreenStyles.controlsWrap}>
                            <View style={discoverScreenStyles.catalogHeader}>
                                <Text style={discoverScreenStyles.catalogEyebrow}>{t("discover.latestEyebrow")}</Text>
                                <Text style={discoverScreenStyles.catalogTitle}>{t("discover.latestTitle")}</Text>
                            </View>
                            <ProductBrowseControls
                                categories={categories}
                                categoryId={categoryId}
                                onChangeCategoryId={setCategoryId}
                                onChangeSort={setSort}
                                sort={sort}
                            />
                        </View>
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
