import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import * as ScreenCapture from "expo-screen-capture"
import { ActivityIndicator, Animated, Image, Platform, Pressable, ScrollView, Text, View, type NativeScrollEvent, type NativeSyntheticEvent } from "react-native"
import { Path, Svg } from "react-native-svg"

import { ContentRail } from "@/components/content/content-rail"
import { SavedIcon } from "@/components/footer/sticky-footer.icons"
import { formatProductPrice } from "@/components/content/product-content"
import { SHARE_ICON_PATH } from "@/components/header/app-header.constants"
import { DetailTemplate } from "@/components/templates/detail-template"
import { useCopyableProfileValue } from "@/hooks/profile/use-copyable-profile-value"
import { useSimilarProducts } from "@/hooks/products/use-similar-products"
import { useRecommendations } from "@/hooks/recommendations/use-recommendations"
import { useProductFavourite } from "@/hooks/products/use-product-favourite"
import { useProduct } from "@/hooks/products/use-product"
import { useLanguage } from "@/providers/language-provider"
import { PRODUCT_REVIEW_COUNT, PRODUCT_REVIEW_RATING } from "@/screens/product/product-screen.constants"
import {
    useProductInfoTabs,
    useProductScreenActions,
    useSelectedProductVariant,
} from "@/screens/product/product-screen.hooks"
import { ProductInfoTabs } from "@/screens/product/product-info-tabs"
import { productScreenStyle } from "@/screens/product/product-screen.styles"
import { ProductScreenProps } from "@/screens/product/product-screen.types"
import { getVariantStockLabel } from "@/screens/product/product-screen.utils"
import { trackRecommendationView } from "@/services/api/recommendations"
import { colors } from "@/theme/colors"

export default function ProductScreen({ productId }: ProductScreenProps) {
    const { product, loading, error } = useProduct(productId)
    const {
        error: favouriteError,
        isFavourite,
        loading: favouriteLoading,
        toggleFavourite,
        updating,
    } = useProductFavourite(productId)
    const { t } = useLanguage()
    const { handleCopy } = useCopyableProfileValue({ t })
    const { handleVariantSelect, selectedVariant } = useSelectedProductVariant(product)
    const { products: similarProducts } = useSimilarProducts(product?.id ?? null, 6)
    const {
        activeInfoTab,
        handleInfoTabChange,
        handleInfoTabLayout,
        infoTabIndicatorWidth,
        infoTabIndicatorX,
        showIndicator,
    } = useProductInfoTabs(product?.id ?? null)
    const { handleBookmarkPress, handleCopyShareLink, handleSharePress } = useProductScreenActions({
        favouriteError,
        isFavourite,
        productId,
        t,
        toggleFavourite,
    })
    const trackedProductIdRef = useRef<number | null>(null)
    const screenshotPromptProgress = useRef(new Animated.Value(0)).current
    const screenshotPromptHideTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const [isScreenshotPromptVisible, setIsScreenshotPromptVisible] = useState(false)
    const [hasCopiedScreenshotLink, setHasCopiedScreenshotLink] = useState(false)
    const {
        hasMore: hasMoreRecommendations,
        loadMore: loadMoreRecommendations,
        loadingMore: recommendationsLoadingMore,
        products: recommendedProducts,
    } = useRecommendations({
        surface: "product",
        productId: product?.id ?? null,
        limit: 6,
        enabled: Boolean(product?.id),
    })

    useEffect(() => {
        if (!product?.id || trackedProductIdRef.current === product.id) {
            return
        }

        trackedProductIdRef.current = product.id
        void trackRecommendationView({ product_id: product.id }).catch(() => undefined)
    }, [product?.id])

    const clearScreenshotPromptTimeout = useCallback(() => {
        if (!screenshotPromptHideTimeoutRef.current) {
            return
        }

        clearTimeout(screenshotPromptHideTimeoutRef.current)
        screenshotPromptHideTimeoutRef.current = null
    }, [])

    const hideScreenshotSharePrompt = useCallback(() => {
        clearScreenshotPromptTimeout()
        screenshotPromptProgress.stopAnimation()
        Animated.timing(screenshotPromptProgress, {
            duration: 180,
            toValue: 0,
            useNativeDriver: true,
        }).start(({ finished }) => {
            if (finished) {
                setIsScreenshotPromptVisible(false)
            }
        })
    }, [clearScreenshotPromptTimeout, screenshotPromptProgress])

    const showScreenshotSharePrompt = useCallback(() => {
        clearScreenshotPromptTimeout()
        setHasCopiedScreenshotLink(false)
        setIsScreenshotPromptVisible(true)
        screenshotPromptProgress.stopAnimation()
        Animated.timing(screenshotPromptProgress, {
            duration: 220,
            toValue: 1,
            useNativeDriver: true,
        }).start()
        screenshotPromptHideTimeoutRef.current = setTimeout(hideScreenshotSharePrompt, 7000)
    }, [clearScreenshotPromptTimeout, hideScreenshotSharePrompt, screenshotPromptProgress])

    useEffect(() => {
        if (Platform.OS === "web") {
            return undefined
        }

        let isMounted = true
        let subscription: ScreenCapture.Subscription | null = null

        void ScreenCapture.isAvailableAsync()
            .then((isAvailable) => {
                if (!isMounted || !isAvailable) {
                    return
                }

                try {
                    subscription = ScreenCapture.addScreenshotListener(showScreenshotSharePrompt)
                } catch {
                    subscription = null
                }
            })
            .catch(() => undefined)

        return () => {
            isMounted = false
            subscription?.remove()
        }
    }, [showScreenshotSharePrompt])

    useEffect(() => () => {
        clearScreenshotPromptTimeout()
    }, [clearScreenshotPromptTimeout])

    const handleScreenshotShareLinkCopy = useCallback(async () => {
        try {
            await handleCopyShareLink()
            setHasCopiedScreenshotLink(true)
            clearScreenshotPromptTimeout()
            screenshotPromptHideTimeoutRef.current = setTimeout(hideScreenshotSharePrompt, 1800)
        } catch {
            setHasCopiedScreenshotLink(false)
        }
    }, [clearScreenshotPromptTimeout, handleCopyShareLink, hideScreenshotSharePrompt])

    const handleRecommendationsScroll = useCallback((event: NativeSyntheticEvent<NativeScrollEvent>) => {
        if (!hasMoreRecommendations || recommendationsLoadingMore) {
            return
        }

        const distanceFromBottom =
            event.nativeEvent.contentSize.height -
            (event.nativeEvent.contentOffset.y + event.nativeEvent.layoutMeasurement.height)

        if (distanceFromBottom <= 240) {
            void loadMoreRecommendations()
        }
    }, [hasMoreRecommendations, loadMoreRecommendations, recommendationsLoadingMore])

    const chromeTemplate = useMemo(
        () => ({
            slots: product
                ? {
                      headerRight: (
                          <View style={productScreenStyle.headerActionsCluster}>
                              <Pressable
                                  accessibilityLabel={t("nav.shareProduct")}
                                  accessibilityRole="button"
                                  onPress={() => {
                                      void handleSharePress()
                                  }}
                                  style={({ pressed }) => [
                                      productScreenStyle.headerActionButton,
                                      pressed && productScreenStyle.bookmarkButtonPressed,
                                  ]}
                              >
                                  <View style={productScreenStyle.shareIcon}>
                                      <Svg width={24} height={24} viewBox="0 0 24 24" fill="none">
                                          <Path d={SHARE_ICON_PATH} fill={colors.mutedText} />
                                      </Svg>
                                  </View>
                              </Pressable>

                              <Pressable
                                  accessibilityLabel={isFavourite ? t("product.favoriteRemoved") : t("product.favoriteAdded")}
                                  accessibilityRole="button"
                                  disabled={favouriteLoading || updating}
                                  onPress={() => {
                                      void handleBookmarkPress()
                                  }}
                                  style={({ pressed }) => [
                                      productScreenStyle.headerActionButton,
                                      (favouriteLoading || updating) && productScreenStyle.bookmarkButtonDisabled,
                                      pressed && productScreenStyle.bookmarkButtonPressed,
                                  ]}
                              >
                                  <SavedIcon color={isFavourite ? colors.favorite : colors.mutedText} />
                              </Pressable>
                          </View>
                      ),
                  }
                : undefined,
            title: product?.name ?? t("route.product"),
        }),
        [favouriteLoading, handleBookmarkPress, handleSharePress, isFavourite, product, t, updating],
    )

    if (loading) {
        return (
            <DetailTemplate chromeTemplate={chromeTemplate} style={productScreenStyle.screen}>
                <View style={productScreenStyle.stateContainer}>
                    <ActivityIndicator />
                </View>
            </DetailTemplate>
        )
    }

    if (error || !product) {
        return (
            <DetailTemplate chromeTemplate={chromeTemplate} style={productScreenStyle.screen}>
                <View style={productScreenStyle.stateContainer}>
                    <Text style={productScreenStyle.stateText}>{t("product.notFound")}</Text>
                </View>
            </DetailTemplate>
        )
    }

    const selectedVariantStockLabel = selectedVariant
        ? getVariantStockLabel(selectedVariant.stock, t)
        : null
    const selectedVariantPriceLabel = formatProductPrice(selectedVariant?.price)
    const heroImageUrl =
        selectedVariant?.image_url ||
        product.variants.find((variant) => Boolean(variant.image_url))?.image_url ||
        product.image_url
    const screenshotPromptTranslateY = screenshotPromptProgress.interpolate({
        inputRange: [0, 1],
        outputRange: [112, 0],
    })

    return (
        <DetailTemplate chromeTemplate={chromeTemplate} style={productScreenStyle.screen}>
            <ScrollView
                style={productScreenStyle.container}
                contentContainerStyle={productScreenStyle.content}
                onScroll={handleRecommendationsScroll}
                scrollEventThrottle={16}
                showsVerticalScrollIndicator={false}
            >
                <View style={productScreenStyle.imageCard}>
                    <Image
                        source={{ uri: heroImageUrl }}
                        style={productScreenStyle.image}
                        resizeMode="cover"
                    />
                    {selectedVariantPriceLabel ? (
                        <View style={productScreenStyle.priceInlineWrap}>
                            <Text style={productScreenStyle.priceInline}>{selectedVariantPriceLabel}</Text>
                        </View>
                    ) : null}
                </View>

                <View style={productScreenStyle.sectionWrap}>
                    {product.variants.length ? (
                        <View style={productScreenStyle.variantCard}>
                            <ScrollView
                                horizontal
                                contentContainerStyle={productScreenStyle.variantImageRow}
                                showsHorizontalScrollIndicator={false}
                            >
                                {product.variants.map((variant) => {
                                    const isSelected = variant.id === selectedVariant?.id
                                    const isDisabled = variant.stock === 0

                                    return (
                                        <Pressable
                                            key={variant.id}
                                            accessibilityLabel={variant.name}
                                            accessibilityRole="button"
                                            disabled={isDisabled}
                                            onPress={() => handleVariantSelect(variant.id)}
                                            style={({ pressed }) => [
                                                productScreenStyle.variantImageOption,
                                                isSelected && productScreenStyle.variantImageOptionSelected,
                                                isDisabled && productScreenStyle.variantImageOptionDisabled,
                                                pressed && productScreenStyle.variantImageOptionPressed,
                                            ]}
                                        >
                                            <Image
                                                source={{ uri: variant.image_url || product.image_url }}
                                                style={[
                                                    productScreenStyle.variantImage,
                                                    isSelected && productScreenStyle.variantImageSelectedBorder,
                                                ]}
                                                resizeMode="cover"
                                            />
                                        </Pressable>
                                    )
                                })}
                            </ScrollView>
                            <Text numberOfLines={1} style={productScreenStyle.variantSelectedLabel}>
                                {selectedVariant?.name ?? ""}
                            </Text>
                            {selectedVariantStockLabel ? (
                                <Text numberOfLines={1} style={productScreenStyle.variantTriggerStatus}>
                                    {selectedVariantStockLabel}
                                </Text>
                            ) : null}
                        </View>
                    ) : null}

                    <View style={productScreenStyle.sectionStack}>
                        <ProductInfoTabs
                            activeInfoTab={activeInfoTab}
                            indicatorWidth={infoTabIndicatorWidth}
                            indicatorX={infoTabIndicatorX}
                            onChangeTab={handleInfoTabChange}
                            onCopySku={handleCopy}
                            onTabLayout={handleInfoTabLayout}
                            product={product}
                            reviewCount={PRODUCT_REVIEW_COUNT}
                            reviewRating={PRODUCT_REVIEW_RATING}
                            showIndicator={showIndicator}
                            t={t}
                        />
                    </View>

                    {similarProducts.length || recommendedProducts.length ? (
                        <View style={productScreenStyle.recommendationStack}>
                            {similarProducts.length ? (
                                <View style={productScreenStyle.similarRailCard}>
                                    <ContentRail
                                        title={t("similarProducts.title")}
                                        description={t("similarProducts.description")}
                                        products={similarProducts}
                                        carouselEdgeInset={16}
                                    />
                                </View>
                            ) : null}

                            {recommendedProducts.length ? (
                                <ContentRail
                                    title={t("recommendations.title")}
                                    description={t("recommendations.productDescription")}
                                    layout="grid"
                                    gridVariant="discover"
                                    mergeHeaderWithFirstRow
                                    loadingMore={recommendationsLoadingMore}
                                    products={recommendedProducts}
                                />
                            ) : null}
                        </View>
                    ) : null}
                </View>
            </ScrollView>

            {isScreenshotPromptVisible ? (
                <Animated.View
                    style={[
                        productScreenStyle.screenshotSharePrompt,
                        {
                            opacity: screenshotPromptProgress,
                            transform: [{ translateY: screenshotPromptTranslateY }],
                        },
                    ]}
                >
                    <View style={productScreenStyle.screenshotSharePromptCopy}>
                        <Text style={productScreenStyle.screenshotSharePromptTitle}>
                            {t("product.screenshotSharePromptTitle")}
                        </Text>
                        <Text style={productScreenStyle.screenshotSharePromptDescription}>
                            {t("product.screenshotSharePromptDescription")}
                        </Text>
                    </View>
                    <Pressable
                        accessibilityLabel={t("product.screenshotSharePromptCta")}
                        accessibilityRole="button"
                        onPress={() => {
                            void handleScreenshotShareLinkCopy()
                        }}
                        style={({ pressed }) => [
                            productScreenStyle.screenshotSharePromptButton,
                            pressed && productScreenStyle.screenshotSharePromptButtonPressed,
                        ]}
                    >
                        <Text style={productScreenStyle.screenshotSharePromptButtonText}>
                            {hasCopiedScreenshotLink
                                ? t("product.screenshotSharePromptCopied")
                                : t("product.screenshotSharePromptCta")}
                        </Text>
                    </Pressable>
                </Animated.View>
            ) : null}
        </DetailTemplate>
    )
}
