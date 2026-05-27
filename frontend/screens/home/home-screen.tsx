import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
    ActivityIndicator,
    Alert,
    Image,
    Pressable,
    useColorScheme,
    ScrollView,
    Text,
    TextInput,
    useWindowDimensions,
    View,
} from "react-native"
import type { LayoutChangeEvent, NativeScrollEvent, NativeSyntheticEvent } from "react-native"
import { useRouter } from "expo-router"
import { LinearGradient } from "expo-linear-gradient"
import { Path, Svg } from "react-native-svg"
import { useSafeAreaInsets } from "react-native-safe-area-context"

import { ContentRail } from "@/components/content/content-rail"
import { HeaderMenu, HeaderMenuPopup } from "@/components/header/header-menu"
import { getHeaderStyles } from "@/components/header/app-header.styles"
import { CatalogTemplate } from "@/components/templates/catalog-template"
import { ROUTES, getProductRoute } from "@/constants/routes"
import { useBanners } from "@/hooks/home/use-banners"
import { useProductCategories } from "@/hooks/products/use-product-categories"
import { useInfiniteProductCatalog } from "@/hooks/products/use-infinite-product-catalog"
import { useProductSearch } from "@/hooks/products/use-product-search"
import { useRecommendations } from "@/hooks/recommendations/use-recommendations"
import { useAuth } from "@/providers/auth-provider"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import { deleteOrderDraft, getOrderDrafts } from "@/services/api/order-drafts"
import { API_BASE_URL } from "@/services/api/constants"
import type { OrderDraftRead } from "@/services/api/order-drafts.types"
import { getOrders } from "@/services/api/orders"
import type { OrderRead, OrderStatusCode } from "@/services/api/orders.types"
import { clearOrderDraftSnapshot, getOrderDraftSnapshot } from "@/hooks/order-draft/order-draft-store"
import { getDraftUpdateErrorMessage } from "@/components/content/recent-order-drafts-rail.utils"
import { getDiscoverCategoryIcon } from "@/screens/discover/discover-category-icons"
import { homeScreenStyles } from "@/screens/home/home-screen.styles"
import { colors, lightColors, type ThemeAccentName } from "@/theme/colors"
import type { Banner } from "@/types/banner"
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
const BANNER_AUTOPLAY_INTERVAL_MS = 5000
const HOME_MENU_POPUP_VERTICAL_OFFSET = 61

function getHomeGradientColors(accentName: ThemeAccentName, isDarkMode: boolean) {
    if (accentName === "blackWhite") {
        return isDarkMode
            ? (["#0B0D10", "#24212E"] as const)
            : (["#FFFFFF", "#DDE7F3"] as const)
    }

    const gradientCombos: Record<Exclude<ThemeAccentName, "blackWhite">, readonly [string, string]> = {
        vividBlue: ["#0A84FF", "#7C3AED"],
        archivedBlue: ["#1F649B", "#00B8D9"],
        teal: ["#FFB300", "#FF4D6D"],
        emerald: ["#0F9F6E", "#B0124F"],
        rose: ["#8A3FFC", "#00A3FF"],
        amber: ["#16A34A", "#FACC15"],
    }

    return gradientCombos[accentName]
}
const orderStatusColors = {
    created: {
        label: "Заказ создан",
        bg: "#F3F4F6",
        text: "#374151",
    },
    invoice_sent: {
        label: "Ожидаем оплату",
        bg: "#FEF3C7",
        text: "#92400E",
    },
    paid: {
        label: "Оплачен",
        bg: "#DCFCE7",
        text: "#166534",
    },
    waiting_response: {
        label: "Ждём ваш ответ",
        bg: "#EDE9FE",
        text: "#5B21B6",
    },
    packaged: {
        label: "Собираем заказ",
        bg: "#DBEAFE",
        text: "#1E40AF",
    },
    sent: {
        label: "В пути",
        bg: "#E0F2FE",
        text: "#075985",
    },
    delivered: {
        label: "Готов к выдаче",
        bg: "#CCFBF1",
        text: "#0F766E",
    },
    completed: {
        label: "Получен",
        bg: "#ECFDF5",
        text: "#047857",
    },
    canceled: {
        label: "Отменён",
        bg: "#FEE2E2",
        text: "#991B1B",
    },
    refund_declined: {
        label: "Возврат отклонён",
        bg: "#FFE4E6",
        text: "#9F1239",
    },
} satisfies Record<OrderStatusCode, { label: string; bg: string; text: string }>

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
    const { height: windowHeight } = useWindowDimensions()
    const homeHeaderMenuStyles = getHeaderStyles(topInset, windowHeight)
    const { language, setLanguage, t } = useLanguage()
    const { accentName, accentPalette, themeName, toggleTheme } = useTheme()
    const { isAuthenticated, signOut } = useAuth()
    const { banners } = useBanners(true)
    const { categories } = useProductCategories(true)
    const { loading: isSearchLoading, products: searchedProducts, query, setQuery } = useProductSearch(true)
    const {
        hasMore: hasMoreRecommendations,
        loadMore: loadMoreRecommendations,
        products: recommendedProducts,
        loadingMore: recommendationsLoadingMore,
    } = useRecommendations({ surface: "home" })
    const {
        hasMore: hasMoreGuestCatalog,
        loadMore: loadMoreGuestCatalog,
        products: guestCatalogProducts,
        loadingMore: guestCatalogLoadingMore,
    } = useInfiniteProductCatalog({
        enabled: !isAuthenticated,
        pageSize: 8,
        sort: "newest",
    })
    const [orderDrafts, setOrderDrafts] = useState<OrderDraftRead[]>([])
    const [isLoadingOrderDrafts, setIsLoadingOrderDrafts] = useState(false)
    const [activeOrders, setActiveOrders] = useState<OrderRead[]>([])
    const [isLoadingActiveOrders, setIsLoadingActiveOrders] = useState(false)
    const [deletingDraftIds, setDeletingDraftIds] = useState<number[]>([])
    const [activeBannerIndex, setActiveBannerIndex] = useState(0)
    const [bannerWidth, setBannerWidth] = useState(0)
    const [isHomeMenuOpen, setIsHomeMenuOpen] = useState(false)
    const bannerScrollRef = useRef<ScrollView>(null)

    const hasSearchQuery = query.trim().length > 0
    const isDarkMode = colorScheme === "dark"
    const topGradientColors = useMemo(
        () => getHomeGradientColors(accentName, isDarkMode),
        [accentName, isDarkMode],
    )
    const quickCatalogIconBackground = accentPalette.primary
    const searchPlaceholderColor = lightColors.mutedText
    const searchTextColor = lightColors.text
    const searchFieldBackgroundColor = lightColors.surface
    const searchPreviewProducts = useMemo(() => searchedProducts.slice(0, 4), [searchedProducts])
    const quickCatalogCategories = useMemo(
        () => categories.filter((category) => getDiscoverCategoryIcon(category.id)),
        [categories],
    )
    const visibleBanners = useMemo<(Banner | null)[]>(() => (banners.length > 0 ? banners : [null]), [banners])
    const bannerCount = visibleBanners.length
    const recommendationRailProducts = isAuthenticated ? recommendedProducts : guestCatalogProducts
    const recommendationRailLoadingMore = isAuthenticated ? recommendationsLoadingMore : guestCatalogLoadingMore
    const hasMoreRecommendationRail = isAuthenticated ? hasMoreRecommendations : hasMoreGuestCatalog
    const loadMoreRecommendationRail = isAuthenticated ? loadMoreRecommendations : loadMoreGuestCatalog
    const shouldShowActiveOrdersSection = isLoadingActiveOrders || activeOrders.length > 0
    const shouldShowDraftsSection = isLoadingOrderDrafts || orderDrafts.length > 0
    const shouldShowOrdersBlock = isAuthenticated && (shouldShowActiveOrdersSection || shouldShowDraftsSection)
    const isDraftDeleting = useCallback((draftId: number) => deletingDraftIds.includes(draftId), [deletingDraftIds])
    const activeOrderCardToneStyle = isDarkMode
        ? null
        : {
            backgroundColor: colors.surface,
        }
    const activeOrderImagesToneStyle = isDarkMode
        ? null
        : {
            backgroundColor: colors.surfaceMuted,
        }
    const activeOrderImagePlaceholderToneStyle = isDarkMode
        ? null
        : {
            backgroundColor: colors.borderSoft,
        }
    const activeOrderSubtitleToneStyle = isDarkMode
        ? null
        : {
            color: colors.text,
        }
    const activeOrderMetaToneStyle = isDarkMode
        ? null
        : {
            color: colors.stateText,
        }

    const handleDeleteDraft = useCallback(async (draftId: number) => {
        if (deletingDraftIds.includes(draftId)) {
            return
        }

        setDeletingDraftIds((currentIds) => [...currentIds, draftId])

        try {
            await deleteOrderDraft(draftId)
            if (getOrderDraftSnapshot()?.id === draftId) {
                clearOrderDraftSnapshot()
            }
            setOrderDrafts((currentDrafts) => currentDrafts.filter((draft) => draft.id !== draftId))
        } catch (deleteError) {
            Alert.alert(getDraftUpdateErrorMessage(deleteError, t("cart.recentDraftsDeleteFailed")))
        } finally {
            setDeletingDraftIds((currentIds) => currentIds.filter((id) => id !== draftId))
        }
    }, [deletingDraftIds, t])

    const handleConfirmDeleteDraft = useCallback((draftId: number) => {
        Alert.alert(
            t("cart.recentDraftsDeleteConfirmTitle"),
            t("cart.recentDraftsDeleteConfirmMessage"),
            [
                {
                    text: t("common.cancel"),
                    style: "cancel",
                },
                {
                    text: t("cart.recentDraftsDeleteAction"),
                    style: "destructive",
                    onPress: () => {
                        void handleDeleteDraft(draftId)
                    },
                },
            ],
        )
    }, [handleDeleteDraft, t])

    const handleHomeScroll = useCallback((event: NativeSyntheticEvent<NativeScrollEvent>) => {
        const { contentOffset, contentSize, layoutMeasurement } = event.nativeEvent
        const distanceFromBottom = contentSize.height - (layoutMeasurement.height + contentOffset.y)
        if (distanceFromBottom < 360 && hasMoreRecommendationRail && !recommendationRailLoadingMore) {
            void loadMoreRecommendationRail()
        }
    }, [hasMoreRecommendationRail, loadMoreRecommendationRail, recommendationRailLoadingMore])

    const handleBannerLayout = useCallback((event: LayoutChangeEvent) => {
        const nextWidth = Math.round(event.nativeEvent.layout.width)
        setBannerWidth((currentWidth) => (currentWidth === nextWidth ? currentWidth : nextWidth))
    }, [])

    const handleBannerScrollEnd = useCallback(
        (event: NativeSyntheticEvent<NativeScrollEvent>) => {
            if (bannerWidth <= 0) {
                return
            }

            const nextIndex = Math.round(event.nativeEvent.contentOffset.x / bannerWidth)
            setActiveBannerIndex(Math.min(Math.max(nextIndex, 0), bannerCount - 1))
        },
        [bannerCount, bannerWidth],
    )

    useEffect(() => {
        if (!isAuthenticated) {
            setOrderDrafts([])
            setIsLoadingOrderDrafts(false)
            setActiveOrders([])
            setIsLoadingActiveOrders(false)
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

    useEffect(() => {
        if (!isAuthenticated) {
            setActiveOrders([])
            setIsLoadingActiveOrders(false)
            return
        }

        let isCancelled = false
        setIsLoadingActiveOrders(true)

        void getOrders({ history_bucket: "active", limit: 12 })
            .then((orders) => {
                if (!isCancelled) {
                    setActiveOrders(orders)
                }
            })
            .catch(() => {
                if (!isCancelled) {
                    setActiveOrders([])
                }
            })
            .finally(() => {
                if (!isCancelled) {
                    setIsLoadingActiveOrders(false)
                }
            })

        return () => {
            isCancelled = true
        }
    }, [isAuthenticated])

    useEffect(() => {
        if (activeBannerIndex < bannerCount) {
            return
        }

        setActiveBannerIndex(0)
        bannerScrollRef.current?.scrollTo({ animated: false, x: 0 })
    }, [activeBannerIndex, bannerCount])

    useEffect(() => {
        if (bannerCount <= 1 || bannerWidth <= 0) {
            return
        }

        const intervalId = setInterval(() => {
            setActiveBannerIndex((currentIndex) => {
                const nextIndex = (currentIndex + 1) % bannerCount
                bannerScrollRef.current?.scrollTo({ animated: true, x: nextIndex * bannerWidth })
                return nextIndex
            })
        }, BANNER_AUTOPLAY_INTERVAL_MS)

        return () => {
            clearInterval(intervalId)
        }
    }, [bannerCount, bannerWidth])

    const handleBannerPress = (banner: Banner | null) => {
        const target = resolveDiscoverRoute(banner?.inner_link)
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
                <View
                    style={[
                        homeScreenStyles.topGradientSectionWrap,
                        isHomeMenuOpen && homeScreenStyles.topGradientSectionWrapMenuOpen,
                    ]}
                >
                    <LinearGradient
                        colors={topGradientColors}
                        end={{ x: 1, y: 0 }}
                        start={{ x: 0, y: 0 }}
                        style={homeScreenStyles.topGradientSection}
                    >
                        <View style={[homeScreenStyles.topGradientContent, { paddingTop: topInset + 14 }]}>
                            <View style={[homeScreenStyles.searchInputWrap, { backgroundColor: searchFieldBackgroundColor }]}>
                                <View style={homeScreenStyles.searchIconWrap}>
                                    <Svg width={18} height={18} viewBox="0 0 24 24" fill="none">
                                        <Path
                                            d="M11 4a7 7 0 1 0 4.47 12.39l4.07 4.08 1.42-1.42-4.08-4.07A7 7 0 0 0 11 4Zm0 2a5 5 0 1 1 0 10 5 5 0 0 1 0-10Z"
                                            fill={searchPlaceholderColor}
                                        />
                                    </Svg>
                                </View>
                                <TextInput
                                    autoCapitalize="none"
                                    autoCorrect={false}
                                    onChangeText={setQuery}
                                    placeholder={t("discover.searchPlaceholder")}
                                    placeholderTextColor={searchPlaceholderColor}
                                    returnKeyType="search"
                                    style={[homeScreenStyles.searchInput, { color: searchTextColor }]}
                                    value={query}
                                />
                                <View style={homeScreenStyles.searchInputActions}>
                                    {isSearchLoading ? <ActivityIndicator color={accentPalette.primary} size="small" /> : null}
                                    <HeaderMenu
                                        isOpen={isHomeMenuOpen}
                                        isAuthenticated={isAuthenticated}
                                        onClose={() => setIsHomeMenuOpen(false)}
                                        onOpenContacts={() => {
                                            setIsHomeMenuOpen(false)
                                            router.push(ROUTES.contacts)
                                        }}
                                        onOpenPublicOffer={() => {
                                            setIsHomeMenuOpen(false)
                                            router.push(ROUTES.publicOffer)
                                        }}
                                        onOpenRequisites={() => {
                                            setIsHomeMenuOpen(false)
                                            router.push(ROUTES.requisites)
                                        }}
                                        onSignIn={() => {
                                            setIsHomeMenuOpen(false)
                                            router.push(ROUTES.login)
                                        }}
                                        onSignOut={signOut}
                                        onSetLanguage={setLanguage}
                                        onToggleTheme={toggleTheme}
                                        onToggle={() => setIsHomeMenuOpen((currentValue) => !currentValue)}
                                        renderPopup={false}
                                        styles={homeHeaderMenuStyles}
                                        t={t}
                                        accentColor={accentPalette.primary}
                                        language={language}
                                        themeName={themeName}
                                    />
                                </View>
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
                    {isHomeMenuOpen ? (
                        <HeaderMenuPopup
                            isAuthenticated={isAuthenticated}
                            onClose={() => setIsHomeMenuOpen(false)}
                            onOpenContacts={() => {
                                setIsHomeMenuOpen(false)
                                router.push(ROUTES.contacts)
                            }}
                            onOpenPublicOffer={() => {
                                setIsHomeMenuOpen(false)
                                router.push(ROUTES.publicOffer)
                            }}
                            onOpenRequisites={() => {
                                setIsHomeMenuOpen(false)
                                router.push(ROUTES.requisites)
                            }}
                            onSignIn={() => {
                                setIsHomeMenuOpen(false)
                                router.push(ROUTES.login)
                            }}
                            onSignOut={signOut}
                            onSetLanguage={setLanguage}
                            onToggleTheme={toggleTheme}
                            popupStyle={[
                                homeScreenStyles.homeMenuPopup,
                                { top: topInset + HOME_MENU_POPUP_VERTICAL_OFFSET },
                            ]}
                            styles={homeHeaderMenuStyles}
                            t={t}
                            accentColor={accentPalette.primary}
                            language={language}
                            themeName={themeName}
                        />
                    ) : null}
                </View>
                <View style={homeScreenStyles.promoBannerSection}>
                    <View style={homeScreenStyles.promoBanner}>
                        <View style={homeScreenStyles.promoBannerViewport} onLayout={handleBannerLayout}>
                            <ScrollView
                                ref={bannerScrollRef}
                                bounces={false}
                                decelerationRate="fast"
                                horizontal
                                onMomentumScrollEnd={handleBannerScrollEnd}
                                pagingEnabled
                                scrollEnabled={bannerCount > 1}
                                scrollEventThrottle={16}
                                showsHorizontalScrollIndicator={false}
                                style={homeScreenStyles.promoBannerCarousel}
                            >
                                {visibleBanners.map((banner, index) => {
                                    const bannerImageSource = resolveBannerImageSource(
                                        banner?.image_path,
                                        banner?.updated_at,
                                    )
                                    return (
                                        <Pressable
                                            key={banner?.id ?? `fallback-banner-${index}`}
                                            accessibilityRole="button"
                                            accessibilityLabel={t("discover.latestTitle")}
                                            onPress={() => handleBannerPress(banner)}
                                            style={({ pressed }) => [
                                                homeScreenStyles.promoBannerTap,
                                                bannerWidth > 0 ? { width: bannerWidth } : null,
                                                pressed && homeScreenStyles.promoBannerPressed,
                                            ]}
                                        >
                                            <Image
                                                source={bannerImageSource}
                                                resizeMode="contain"
                                                style={homeScreenStyles.promoImage}
                                            />
                                        </Pressable>
                                    )
                                })}
                            </ScrollView>
                            {banners.length > 0 ? (
                                <View pointerEvents="none" style={homeScreenStyles.promoBannerIndicators}>
                                    {visibleBanners.map((banner, index) => (
                                        <View
                                            key={banner?.id ?? `fallback-banner-indicator-${index}`}
                                            style={[
                                                homeScreenStyles.promoBannerIndicator,
                                                index === activeBannerIndex && homeScreenStyles.promoBannerIndicatorActive,
                                            ]}
                                        />
                                    ))}
                                </View>
                            ) : null}
                        </View>
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
                                                {CategoryIcon ? <CategoryIcon width={30} height={30} color="#FFFFFF" /> : null}
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

                {shouldShowOrdersBlock ? (
                    <View style={homeScreenStyles.ordersBlock}>
                        {shouldShowActiveOrdersSection ? (
                            <>
                                <View style={homeScreenStyles.ordersHeader}>
                                    <Text style={homeScreenStyles.ordersTitle}>Заказы</Text>
                                </View>

                                {isLoadingActiveOrders ? (
                                    <View style={homeScreenStyles.orderLoadingWrap}>
                                        <ActivityIndicator color={accentPalette.primary} />
                                    </View>
                                ) : (
                                    <ScrollView horizontal contentContainerStyle={homeScreenStyles.activeOrdersRow} showsHorizontalScrollIndicator={false}>
                                        {activeOrders.map((order) => {
                                            const statusDisplay = orderStatusColors[order.status_code] ?? orderStatusColors.created
                                            const subtitle = order.delivery_string || order.delivery_address?.full_address || "—"
                                            const orderItemsPreview = order.items.slice(0, 4)
                                            const isSingleOrderImage = orderItemsPreview.length <= 1

                                            return (
                                                <Pressable
                                                    key={order.id}
                                                    accessibilityLabel={`${t("home.activeOrdersOpen")} #${order.order_number}`}
                                                    accessibilityRole="button"
                                                    onPress={() => {
                                                        router.push({ pathname: ROUTES.payment, params: { orderId: String(order.id) } })
                                                    }}
                                                    style={({ pressed }) => [
                                                        homeScreenStyles.activeOrderCard,
                                                        activeOrderCardToneStyle,
                                                        pressed && homeScreenStyles.activeOrderCardPressed,
                                                    ]}
                                                >
                                                    <View style={[homeScreenStyles.activeOrderImages, activeOrderImagesToneStyle]}>
                                                        {orderItemsPreview.length ? (
                                                            orderItemsPreview.map((item) => (
                                                                item.image_url ? (
                                                                    <Image
                                                                        key={`${order.id}-${item.id}-${item.variant_id}`}
                                                                        source={{ uri: item.image_url }}
                                                                        style={[
                                                                            homeScreenStyles.activeOrderImage,
                                                                            isSingleOrderImage && homeScreenStyles.activeOrderImageSingle,
                                                                        ]}
                                                                        resizeMode="contain"
                                                                    />
                                                                ) : (
                                                                    <View
                                                                        key={`${order.id}-${item.id}-${item.variant_id}`}
                                                                        style={[
                                                                            homeScreenStyles.activeOrderImagePlaceholder,
                                                                            activeOrderImagePlaceholderToneStyle,
                                                                            isSingleOrderImage && homeScreenStyles.activeOrderImageSingle,
                                                                        ]}
                                                                    />
                                                                )
                                                            ))
                                                        ) : (
                                                            <View
                                                                style={[
                                                                    homeScreenStyles.activeOrderImagePlaceholder,
                                                                    activeOrderImagePlaceholderToneStyle,
                                                                    homeScreenStyles.activeOrderImageSingle,
                                                                ]}
                                                            />
                                                        )}
                                                    </View>

                                                    <View style={homeScreenStyles.activeOrderBody}>
                                                        <View style={homeScreenStyles.activeOrderStatusBlock}>
                                                            <View
                                                                style={[
                                                                    homeScreenStyles.activeOrderStatusBadge,
                                                                    { backgroundColor: statusDisplay.bg },
                                                                ]}
                                                            >
                                                                <Text
                                                                    numberOfLines={2}
                                                                    style={[
                                                                        homeScreenStyles.activeOrderStatusText,
                                                                        { color: statusDisplay.text },
                                                                    ]}
                                                                >
                                                                    {statusDisplay.label}
                                                                </Text>
                                                            </View>
                                                            <Text
                                                                numberOfLines={1}
                                                                style={[homeScreenStyles.activeOrderMeta, activeOrderMetaToneStyle]}
                                                            >
                                                                #{order.order_number}
                                                            </Text>
                                                        </View>
                                                        <Text
                                                            numberOfLines={2}
                                                            style={[homeScreenStyles.activeOrderSubtitle, activeOrderSubtitleToneStyle]}
                                                        >
                                                            {`${order.items_count} • ${subtitle}`}
                                                        </Text>
                                                    </View>
                                                </Pressable>
                                            )
                                        })}
                                    </ScrollView>
                                )}
                            </>
                        ) : null}

                        {shouldShowActiveOrdersSection && shouldShowDraftsSection ? (
                            <View style={homeScreenStyles.ordersSeparator} />
                        ) : null}

                        {shouldShowDraftsSection ? (
                            <>
                                <View style={homeScreenStyles.ordersHeader}>
                                    <Text style={homeScreenStyles.ordersTitle}>Продолжите оформление</Text>
                                </View>

                                {isLoadingOrderDrafts ? (
                                    <View style={homeScreenStyles.orderLoadingWrap}>
                                        <ActivityIndicator color={accentPalette.primary} />
                                    </View>
                                ) : (
                                    <ScrollView horizontal contentContainerStyle={homeScreenStyles.ordersRow} showsHorizontalScrollIndicator={false}>
                                        {orderDrafts.map((draft) => {
                                            const total = formatMoney(Number(draft.grand_total), draft.currency)
                                            const deleting = isDraftDeleting(draft.id)
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
                                                    <Pressable
                                                        accessibilityLabel={t("cart.recentDraftsDeleteAction")}
                                                        accessibilityRole="button"
                                                        disabled={deleting}
                                                        hitSlop={10}
                                                        onPress={(event) => {
                                                            event.stopPropagation()
                                                            handleConfirmDeleteDraft(draft.id)
                                                        }}
                                                        style={({ pressed }) => [
                                                            homeScreenStyles.orderCardDeleteBadge,
                                                            deleting && homeScreenStyles.orderCardDeleteBadgeDisabled,
                                                            pressed && homeScreenStyles.orderCardDeleteBadgePressed,
                                                        ]}
                                                    >
                                                        <Svg width={14} height={14} viewBox="0 0 24 24" fill="none">
                                                            <Path
                                                                d="M6 6L18 18"
                                                                stroke="#E11D48"
                                                                strokeLinecap="round"
                                                                strokeWidth={3.2}
                                                            />
                                                            <Path
                                                                d="M18 6L6 18"
                                                                stroke="#E11D48"
                                                                strokeLinecap="round"
                                                                strokeWidth={3.2}
                                                            />
                                                        </Svg>
                                                    </Pressable>
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
                                )}
                            </>
                        ) : null}
                    </View>
                ) : null}

                {recommendationRailProducts.length ? (
                    <View style={homeScreenStyles.recommendationsSection}>
                        <ContentRail
                            title={t("recommendations.title")}
                            description={t("recommendations.productDescription")}
                            layout="grid"
                            gridVariant="discover"
                            mergeHeaderWithFirstRow
                            loadingMore={recommendationRailLoadingMore}
                            products={recommendationRailProducts}
                        />
                    </View>
                ) : null}
            </ScrollView>
        </CatalogTemplate>
    )
}
