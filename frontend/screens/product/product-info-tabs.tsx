import { Animated, Pressable, Text, View } from "react-native"
import { Path, Svg } from "react-native-svg"

import { HtmlContent, hasRenderableHtmlContent } from "@/components/content/html-content"
import {
    REVIEW_STAR_PATH,
} from "@/screens/product/product-screen.constants"
import { productScreenStyle } from "@/screens/product/product-screen.styles"
import type { ProductInfoTabsProps } from "@/screens/product/product-info-tabs.types"

export function ProductInfoTabs({
    activeInfoTab,
    indicatorWidth,
    indicatorX,
    onChangeTab,
    onCopySku,
    onTabLayout,
    product,
    reviewCount,
    reviewRating,
    showIndicator,
    t,
}: ProductInfoTabsProps) {
    const detailsFallback = t("product.detailsNotProvided")
    const overviewHtml = hasRenderableHtmlContent(product.description) ? product.description : null
    const usageHtml = hasRenderableHtmlContent(product.usage) ? product.usage : null
    const expirationHtml = hasRenderableHtmlContent(product.expiration) ? product.expiration : null
    const productSku = product.sku?.trim() || null
    const infoTabs = [
        {
            key: "reviews" as const,
            label: `${t("product.tabReviews")} (${reviewCount})`,
        },
        {
            key: "overview" as const,
            label: t("product.tabOverview"),
        },
        {
            key: "usage" as const,
            label: t("product.tabUsage"),
        },
        {
            key: "details" as const,
            label: t("product.tabDetails"),
        },
    ]

    const renderActiveInfoTab = () => {
        if (activeInfoTab === "overview") {
            return (
                <View style={productScreenStyle.detailsList}>
                    {overviewHtml ? <HtmlContent html={overviewHtml} variant="body" /> : null}
                    {!overviewHtml ? (
                        <Text style={productScreenStyle.detailRichText}>{detailsFallback}</Text>
                    ) : null}

                    <View>
                        {overviewHtml ? <View style={productScreenStyle.detailDivider} /> : null}
                        <View style={productScreenStyle.detailRow}>
                            <Text style={productScreenStyle.detailLabel}>{t("product.skuLabel")}</Text>
                            {productSku ? (
                                <Pressable
                                    accessibilityLabel={productSku}
                                    accessibilityRole="button"
                                    onPress={() => {
                                        void onCopySku(productSku)
                                    }}
                                    style={({ pressed }) => [
                                        productScreenStyle.skuPressable,
                                        pressed && productScreenStyle.skuPressablePressed,
                                    ]}
                                >
                                    <Text
                                        style={[
                                            productScreenStyle.detailValue,
                                            productScreenStyle.detailValueSku,
                                        ]}
                                    >
                                        {productSku}
                                    </Text>
                                </Pressable>
                            ) : (
                                <Text style={productScreenStyle.detailRichText}>{detailsFallback}</Text>
                            )}
                        </View>
                    </View>
                </View>
            )
        }

        if (activeInfoTab === "usage") {
            return usageHtml ? (
                <HtmlContent html={usageHtml} variant="detail" />
            ) : (
                <Text style={productScreenStyle.detailRichText}>{detailsFallback}</Text>
            )
        }

        if (activeInfoTab === "details") {
            return expirationHtml ? (
                <HtmlContent html={expirationHtml} variant="detail" />
            ) : (
                <Text style={productScreenStyle.detailRichText}>{detailsFallback}</Text>
            )
        }

        return (
            <View style={productScreenStyle.reviewsPlaceholder}>
                <View style={productScreenStyle.reviewsSummaryRow}>
                    <Svg width={16} height={16} viewBox="0 0 24 24">
                        <Path d={REVIEW_STAR_PATH} fill="#FFC83D" />
                    </Svg>
                    <Text style={productScreenStyle.reviewsSummaryValue}>{reviewRating}</Text>
                </View>
                <Text style={productScreenStyle.detailRichText}>{detailsFallback}</Text>
            </View>
        )
    }

    return (
        <View style={productScreenStyle.sectionCard}>
            <View style={productScreenStyle.infoTabsHeader}>
                <View style={productScreenStyle.infoTabsRail}>
                    <View style={productScreenStyle.infoTabsRow}>
                        {infoTabs.map((tab) => {
                            const isActive = tab.key === activeInfoTab

                            return (
                                <Pressable
                                    key={tab.key}
                                    accessibilityRole="button"
                                    accessibilityState={{ selected: isActive }}
                                    onLayout={(event) => {
                                        onTabLayout(tab.key, event.nativeEvent.layout)
                                    }}
                                    onPress={() => {
                                        onChangeTab(tab.key)
                                    }}
                                    style={productScreenStyle.infoTabButton}
                                >
                                    <Text
                                        style={[
                                            productScreenStyle.infoTabButtonText,
                                            isActive && productScreenStyle.infoTabButtonTextActive,
                                        ]}
                                    >
                                        {tab.label}
                                    </Text>
                                </Pressable>
                            )
                        })}
                    </View>
                    {showIndicator ? (
                        <Animated.View
                            style={[
                                productScreenStyle.infoTabIndicator,
                                { pointerEvents: "none" },
                                {
                                    transform: [{ translateX: indicatorX }],
                                    width: indicatorWidth,
                                },
                            ]}
                        />
                    ) : null}
                </View>
            </View>
            <View style={productScreenStyle.infoTabContent}>{renderActiveInfoTab()}</View>
        </View>
    )
}
