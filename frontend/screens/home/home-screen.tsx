import { useCallback, useEffect, useMemo, useState } from "react"
import {
    ActivityIndicator,
    Image,
    Pressable,
    useColorScheme,
    ScrollView,
    Text,
    TextInput,
    View,
} from "react-native"
import type { NativeScrollEvent, NativeSyntheticEvent } from "react-native"
import { useRouter } from "expo-router"
import { LinearGradient } from "expo-linear-gradient"
import { Path, Svg } from "react-native-svg"
import { useSafeAreaInsets } from "react-native-safe-area-context"

import { ContentRail } from "@/components/content/content-rail"
import { CatalogTemplate } from "@/components/templates/catalog-template"
import { ROUTES, getProductRoute } from "@/constants/routes"
import { useBanners } from "@/hooks/home/use-banners"
import { useProductCategories } from "@/hooks/products/use-product-categories"
import { useProductSearch } from "@/hooks/products/use-product-search"
import { useRecommendations } from "@/hooks/recommendations/use-recommendations"
import { useAuth } from "@/providers/auth-provider"
import { useLanguage } from "@/providers/language-provider"
import { getOrderDrafts } from "@/services/api/order-drafts"
import { API_BASE_URL } from "@/services/api/constants"
import type { OrderDraftRead } from "@/services/api/order-drafts.types"
import { getDiscoverCategoryIcon } from "@/screens/discover/discover-category-icons"
import { homeScreenStyles } from "@/screens/home/home-screen.styles"
import { colors } from "@/theme/colors"
import { formatMoney } from "@/utils/formatting"

function getMediaBaseUrl(): string {
    const trimmedApiBaseUrl = API_BASE_URL.replace(/\/+$/, "")
    if (!trimmedApiBaseUrl) {
        return ""
    }

    try {
        return new URL(trimmedApiBaseUrl).origin
    } catch {
        return trimmedApiBaseUrl.replace(/\/api$/i, "")
    }
}

const MEDIA_BASE_URL = getMediaBaseUrl()
const FALLBACK_BANNER_IMAGE_VERSION = "square-20260512"

function appendImageVersion(uri: string, version: string | null | undefined): string {
    const trimmedVersion = version?.trim()
    if (!trimmedVersion) {
        return uri
    }

    return `${uri}${uri.includes("?") ? "&" : "?"}v=${encodeURIComponent(trimmedVersion)}`
}

function resolveBannerImageSource(imagePath: string | null | undefined, imageVersion?: string | null): { uri: string } {
    const version = imageVersion ?? FALLBACK_BANNER_IMAGE_VERSION

    if (typeof imagePath === "string" && imagePath.length > 0) {
        if (/^https?:\/\//i.test(imagePath)) {
            if (imagePath.includes("/media/banners/ghk-cu-banner.png")) {
                return {
                    uri: appendImageVersion(
                        imagePath.replace("/media/banners/ghk-cu-banner.png", "/media/banners/ghk-cu-banner.jpg"),
                        version,
                    ),
                }
            }
            return { uri: appendImageVersion(imagePath, version) }
        }

        if (imagePath.startsWith("/")) {
            if (imagePath === "/media/banners/ghk-cu-banner.png") {
                return { uri: appendImageVersion(`${MEDIA_BASE_URL}/media/banners/ghk-cu-banner.jpg`, version) }
            }
            return { uri: appendImageVersion(`${MEDIA_BASE_URL}${imagePath}`, version) }
        }
    }

    return { uri: appendImageVersion(`${MEDIA_BASE_URL}/media/banners/ghk-cu-banner.jpg`, version) }
}

function resolveDiscoverRoute(link: string | null | undefined): { q: string; tab: string } {
    const fallback = { q: "ghk-cu", tab: "products" }
    const trimmedLink = (link ?? "").trim()
    if (!trimmedLink) {
        return fallback
    }

    let candidate: URL
    try {
        candidate = trimmedLink.startsWith("http")
            ? new URL(trimmedLink)
            : new URL(trimmedLink, "https://elixir.local")
    } catch {
        return fallback
    }

    const normalizedPath = candidate.pathname.replace(/\/+$/, "")
    if (normalizedPath !== ROUTES.discover) {
        return fallback
    }

    const q = candidate.searchParams.get("q")?.trim() || fallback.q
    const tab = candidate.searchParams.get("tab")?.trim() || fallback.tab
    return { q, tab }
}

export default function HomeScreen() {
    const router = useRouter()
    const colorScheme = useColorScheme()
    const topInset = useSafeAreaInsets().top
    const { t } = useLanguage()
    const { isAuthenticated } = useAuth()
    const { banners } = useBanners(true)
    const { categories } = useProductCategories(true)
    const { loading: isSearchLoading, products: searchedProducts, query, setQuery } = useProductSearch(true)
    const {
        hasMore: hasMoreRecommendations,
        loadMore: loadMoreRecommendations,
        products: recommendedProducts,
        loadingMore: recommendationsLoadingMore,
    } = useRecommendations({ surface: "home" })
    const [orderDrafts, setOrderDrafts] = useState<OrderDraftRead[]>([])
    const [isLoadingOrderDrafts, setIsLoadingOrderDrafts] = useState(false)

    const hasSearchQuery = query.trim().length > 0
    const isDarkMode = colorScheme === "dark"
    const quickCatalogIconBackground = isDarkMode ? "#2563EB" : colors.primary
    const searchPreviewProducts = useMemo(() => searchedProducts.slice(0, 4), [searchedProducts])
    const quickCatalogCategories = useMemo(
        () => categories.filter((category) => getDiscoverCategoryIcon(category.id)),
        [categories],
    )
    const primaryBanner = banners[0] ?? null
    const bannerImageSource = resolveBannerImageSource(primaryBanner?.image_path, primaryBanner?.updated_at)

    const handleHomeScroll = useCallback((event: NativeSyntheticEvent<NativeScrollEvent>) => {
        const { contentOffset, contentSize, layoutMeasurement } = event.nativeEvent
        const distanceFromBottom = contentSize.height - (layoutMeasurement.height + contentOffset.y)
        if (distanceFromBottom < 360 && hasMoreRecommendations && !recommendationsLoadingMore) {
            void loadMoreRecommendations()
        }
    }, [hasMoreRecommendations, loadMoreRecommendations, recommendationsLoadingMore])

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

    const handleBannerPress = () => {
        const target = resolveDiscoverRoute(primaryBanner?.inner_link)
        router.push({
            pathname: ROUTES.discover,
            params: {
                resetCategory: "1",
                q: target.q,
                tab: target.tab,
            },
        })
    }

    return (
        <CatalogTemplate
            chromeTemplate={{
                header: "none",
                footer: "nav",
            }}
            style={homeScreenStyles.screen}
        >
            <ScrollView
                style={homeScreenStyles.screen}
                contentContainerStyle={homeScreenStyles.content}
                keyboardShouldPersistTaps="handled"
                onScroll={handleHomeScroll}
                scrollEventThrottle={16}
                showsVerticalScrollIndicator={false}
            >
                <View style={homeScreenStyles.topGradientSectionWrap}>
                    <LinearGradient
                        colors={["#FF6F93", "#FF88B0", "#FFC96B"]}
                        end={{ x: 1, y: 0 }}
                        start={{ x: 0, y: 0 }}
                        style={homeScreenStyles.topGradientSection}
                    >
                        <View style={[homeScreenStyles.topGradientContent, { paddingTop: topInset + 14 }]}>
                            <View style={homeScreenStyles.searchInputWrap}>
                                <View style={homeScreenStyles.searchIconWrap}>
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
                                    style={homeScreenStyles.searchInput}
                                    value={query}
                                />
                                {isSearchLoading ? <ActivityIndicator color={colors.primary} size="small" /> : null}
                            </View>

                            {hasSearchQuery && searchPreviewProducts.length ? (
                                <ScrollView
                                    horizontal
                                    contentContainerStyle={homeScreenStyles.searchPreviewRow}
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
                                                homeScreenStyles.searchPreviewCard,
                                                pressed && homeScreenStyles.searchPreviewCardPressed,
                                            ]}
                                        >
                                            {product.image_url ? (
                                                <Image
                                                    source={{ uri: product.image_url }}
                                                    style={homeScreenStyles.searchPreviewThumb}
                                                    resizeMode="cover"
                                                />
                                            ) : (
                                                <View style={homeScreenStyles.searchPreviewThumb} />
                                            )}
                                            <Text numberOfLines={1} style={homeScreenStyles.searchPreviewTitle}>
                                                {product.name}
                                            </Text>
                                        </Pressable>
                                    ))}
                                </ScrollView>
                            ) : null}
                        </View>
                    </LinearGradient>
                </View>
                <View style={homeScreenStyles.promoBannerSection}>
                    <View style={homeScreenStyles.promoBanner}>
                        <Pressable
                            accessibilityRole="button"
                            accessibilityLabel={t("discover.latestTitle")}
                            onPress={handleBannerPress}
                            style={({ pressed }) => [
                                homeScreenStyles.promoBannerTap,
                                pressed && homeScreenStyles.promoBannerPressed,
                            ]}
                        >
                            <Image source={bannerImageSource} resizeMode="contain" style={homeScreenStyles.promoImage} />
                        </Pressable>
                        <View style={homeScreenStyles.quickCatalogInBanner}>
                            <ScrollView
                                horizontal
                                contentContainerStyle={homeScreenStyles.quickCatalogRow}
                                showsHorizontalScrollIndicator={false}
                            >
                                {quickCatalogCategories.map((category) => {
                                    const CategoryIcon = getDiscoverCategoryIcon(category.id)
                                    return (
                                        <Pressable
                                            key={category.id}
                                            accessibilityLabel={category.name}
                                            accessibilityRole="button"
                                            onPress={() => {
                                                router.push({
                                                    pathname: ROUTES.discover,
                                                    params: { categoryId: String(category.id) },
                                                })
                                            }}
                                            style={({ pressed }) => [
                                                homeScreenStyles.quickCatalogItem,
                                                pressed && homeScreenStyles.quickCatalogItemPressed,
                                            ]}
                                        >
                                            <View
                                                style={[
                                                    homeScreenStyles.quickCatalogIcon,
                                                    { backgroundColor: quickCatalogIconBackground },
                                                ]}
                                            >
                                                {CategoryIcon ? (
                                                    <CategoryIcon width={30} height={30} color={colors.onPrimary} />
                                                ) : null}
                                            </View>
                                            <Text
                                                ellipsizeMode="tail"
                                                numberOfLines={2}
                                                style={homeScreenStyles.quickCatalogLabel}
                                            >
                                                {category.name}
                                            </Text>
                                        </Pressable>
                                    )
                                })}
                            </ScrollView>
                        </View>
                    </View>
                </View>

                <View style={homeScreenStyles.ordersBlock}>
                    <View style={homeScreenStyles.ordersHeader}>
                        <Text style={homeScreenStyles.ordersEyebrow}>{t("cart.recentDraftsEyebrow")}</Text>
                        <Text style={homeScreenStyles.ordersTitle}>{t("cart.recentDraftsTitle")}</Text>
                    </View>

                    {!isAuthenticated ? (
                        <Pressable
                            accessibilityLabel={t("auth.entry.login")}
                            accessibilityRole="button"
                            onPress={() => {
                                router.push(ROUTES.login)
                            }}
                            style={({ pressed }) => [
                                homeScreenStyles.orderLoginCard,
                                pressed && homeScreenStyles.orderLoginCardPressed,
                            ]}
                        >
                            <Text style={homeScreenStyles.orderLoginCardText}>{t("cart.openDraftsCta")}</Text>
                        </Pressable>
                    ) : isLoadingOrderDrafts ? (
                        <View style={homeScreenStyles.orderLoadingWrap}>
                            <ActivityIndicator color={colors.primary} />
                        </View>
                    ) : orderDrafts.length ? (
                        <ScrollView horizontal contentContainerStyle={homeScreenStyles.ordersRow} showsHorizontalScrollIndicator={false}>
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
                                        style={({ pressed }) => [homeScreenStyles.orderCard, pressed && homeScreenStyles.orderCardPressed]}
                                    >
                                        <Text numberOfLines={1} style={homeScreenStyles.orderCardTitle}>
                                            #{draft.id}
                                        </Text>
                                        <Text numberOfLines={1} style={homeScreenStyles.orderCardMeta}>
                                            {draft.items_count} {t("cart.positionsLabel")}
                                        </Text>
                                        <Text numberOfLines={1} style={homeScreenStyles.orderCardTotal}>
                                            {total ?? "—"}
                                        </Text>
                                    </Pressable>
                                )
                            })}
                        </ScrollView>
                    ) : (
                        <View style={homeScreenStyles.orderEmptyCard}>
                            <Text style={homeScreenStyles.orderEmptyText}>{t("cart.emptyDescriptionWithDrafts")}</Text>
                        </View>
                    )}
                </View>

                {recommendedProducts.length ? (
                    <View style={homeScreenStyles.recommendationsSection}>
                        <ContentRail
                            title={t("recommendations.title")}
                            description={t("recommendations.productDescription")}
                            layout="grid"
                            gridVariant="discover"
                            mergeHeaderWithFirstRow
                            loadingMore={recommendationsLoadingMore}
                            products={recommendedProducts}
                        />
                    </View>
                ) : null}
            </ScrollView>
        </CatalogTemplate>
    )
}
