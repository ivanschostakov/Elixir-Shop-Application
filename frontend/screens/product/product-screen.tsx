import { useMemo } from "react"
import { ActivityIndicator, Image, Pressable, ScrollView, Text, View } from "react-native"
import { Path, Svg } from "react-native-svg"

import { SavedIcon } from "@/components/footer/sticky-footer.icons"
import { formatProductPrice } from "@/components/content/product-content"
import { SHARE_ICON_PATH } from "@/components/header/app-header.constants"
import { DetailTemplate } from "@/components/templates/detail-template"
import { useCopyableProfileValue } from "@/hooks/profile/use-copyable-profile-value"
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
    const {
        activeInfoTab,
        handleInfoTabChange,
        handleInfoTabLayout,
        infoTabIndicatorWidth,
        infoTabIndicatorX,
        showIndicator,
    } = useProductInfoTabs(product?.id ?? null)
    const { handleBookmarkPress, handleSharePress } = useProductScreenActions({
        favouriteError,
        isFavourite,
        productId,
        t,
        toggleFavourite,
    })

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
                                          <Path d={SHARE_ICON_PATH} fill="#6B7280" />
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

    return (
        <DetailTemplate chromeTemplate={chromeTemplate} style={productScreenStyle.screen}>
            <ScrollView
                style={productScreenStyle.container}
                contentContainerStyle={productScreenStyle.content}
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
                </View>
            </ScrollView>
        </DetailTemplate>
    )
}
