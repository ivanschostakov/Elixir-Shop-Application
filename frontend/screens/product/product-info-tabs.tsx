import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Alert, Animated, Easing, Linking, Pressable, Text, View } from "react-native"
import type { LayoutChangeEvent } from "react-native"

import { HtmlContent, hasRenderableHtmlContent } from "@/components/content/html-content"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useTheme } from "@/providers/theme-provider"
import { createProductScreenStyle } from "@/screens/product/product-screen.styles"
import type { ProductInfoTabKey } from "@/screens/product/product-screen.types"
import type { ProductInfoTabsProps } from "@/screens/product/product-info-tabs.types"

const INFO_TAB_INDICATOR_ANIMATION_MS = 220

type InfoTabLayout = {
    width: number
    x: number
}

function formatCertificateSize(sizeBytes: number, t: ProductInfoTabsProps["t"]) {
    if (!Number.isFinite(sizeBytes) || sizeBytes <= 0) {
        return t("product.certificateFile")
    }
    if (sizeBytes >= 1024 * 1024) {
        return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`
    }
    if (sizeBytes >= 1024) {
        return `${Math.round(sizeBytes / 1024)} KB`
    }
    return `${sizeBytes} B`
}

export function ProductInfoTabs({
    activeInfoTab,
    onChangeTab,
    onCopySku,
    product,
    t,
}: ProductInfoTabsProps) {
    const productScreenStyle = useThemeStyles(createProductScreenStyle)
    const { accentPalette, themeName } = useTheme()
    const detailsFallback = t("product.detailsNotProvided")
    const overviewHtml = hasRenderableHtmlContent(product.description) ? product.description : null
    const usageHtml = hasRenderableHtmlContent(product.usage) ? product.usage : null
    const expirationHtml = hasRenderableHtmlContent(product.expiration) ? product.expiration : null
    const certificates = product.certificates ?? []
    const productSku = product.sku?.trim() || null
    const [infoTabLayouts, setInfoTabLayouts] = useState<Partial<Record<ProductInfoTabKey, InfoTabLayout>>>({})
    const infoTabIndicatorX = useRef(new Animated.Value(0)).current
    const infoTabIndicatorWidth = useRef(new Animated.Value(0)).current
    const hasMountedInfoTabIndicator = useRef(false)
    const infoTabs = useMemo(
        () => [
            { key: "overview" as const, label: t("product.tabOverview") },
            { key: "usage" as const, label: t("product.tabUsage") },
            { key: "details" as const, label: t("product.tabDetails") },
            ...(certificates.length
                ? [{ key: "certificates" as const, label: t("product.tabCertificates") }]
                : []),
        ],
        [certificates.length, t],
    )
    const activeInfoTabLayout = infoTabLayouts[activeInfoTab]

    const handleInfoTabLayout = useCallback((tabKey: ProductInfoTabKey, event: LayoutChangeEvent) => {
        const { width, x } = event.nativeEvent.layout
        setInfoTabLayouts((currentLayouts) => {
            const existingLayout = currentLayouts[tabKey]
            if (existingLayout && existingLayout.width === width && existingLayout.x === x) {
                return currentLayouts
            }
            return { ...currentLayouts, [tabKey]: { width, x } }
        })
    }, [])

    useEffect(() => {
        if (!activeInfoTabLayout) {
            return
        }
        if (!hasMountedInfoTabIndicator.current) {
            infoTabIndicatorX.setValue(activeInfoTabLayout.x)
            infoTabIndicatorWidth.setValue(activeInfoTabLayout.width)
            hasMountedInfoTabIndicator.current = true
            return
        }
        Animated.parallel([
            Animated.timing(infoTabIndicatorX, {
                duration: INFO_TAB_INDICATOR_ANIMATION_MS,
                easing: Easing.out(Easing.cubic),
                toValue: activeInfoTabLayout.x,
                useNativeDriver: false,
            }),
            Animated.timing(infoTabIndicatorWidth, {
                duration: INFO_TAB_INDICATOR_ANIMATION_MS,
                easing: Easing.out(Easing.cubic),
                toValue: activeInfoTabLayout.width,
                useNativeDriver: false,
            }),
        ]).start()
    }, [activeInfoTabLayout, infoTabIndicatorWidth, infoTabIndicatorX])

    const renderActiveInfoTab = () => {
        if (activeInfoTab === "overview") {
            return (
                <View style={productScreenStyle.detailsList}>
                    {overviewHtml ? <HtmlContent html={overviewHtml} variant="body" /> : null}
                    {!overviewHtml ? <Text style={productScreenStyle.detailRichText}>{detailsFallback}</Text> : null}
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
                                            { color: accentPalette.primary },
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
            return usageHtml
                ? <HtmlContent html={usageHtml} variant="detail" />
                : <Text style={productScreenStyle.detailRichText}>{detailsFallback}</Text>
        }
        if (activeInfoTab === "details") {
            return expirationHtml
                ? <HtmlContent html={expirationHtml} variant="detail" />
                : <Text style={productScreenStyle.detailRichText}>{detailsFallback}</Text>
        }
        return (
            <View style={productScreenStyle.certificateList}>
                {certificates.map((certificate) => (
                    <Pressable
                        key={certificate.id}
                        accessibilityLabel={certificate.title}
                        accessibilityRole="link"
                        onPress={() => {
                            void Linking.openURL(certificate.url).catch(() => {
                                Alert.alert(
                                    t("product.certificateOpenFailedTitle"),
                                    t("product.certificateOpenFailedMessage"),
                                )
                            })
                        }}
                        style={({ pressed }) => [
                            productScreenStyle.certificateRow,
                            pressed && productScreenStyle.certificateRowPressed,
                        ]}
                    >
                        <View style={productScreenStyle.certificateFileBadge}>
                            <Text style={productScreenStyle.certificateFileBadgeText}>
                                {certificate.content_type?.includes("pdf")
                                    ? "PDF"
                                    : t("product.certificateFile")}
                            </Text>
                        </View>
                        <View style={productScreenStyle.certificateCopy}>
                            <Text style={productScreenStyle.certificateTitle}>
                                {certificate.title}
                            </Text>
                            <Text style={productScreenStyle.certificateMeta}>
                                {formatCertificateSize(certificate.size_bytes, t)}
                            </Text>
                        </View>
                        <Text style={productScreenStyle.certificateOpenIcon}>↗</Text>
                    </Pressable>
                ))}
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
                                    onLayout={(event) => handleInfoTabLayout(tab.key, event)}
                                    onPress={() => onChangeTab(tab.key)}
                                    style={productScreenStyle.infoTabButton}
                                >
                                    <Text
                                        style={[
                                            productScreenStyle.infoTabButtonText,
                                            isActive && productScreenStyle.infoTabButtonTextActive,
                                            {
                                                color: isActive
                                                    ? (themeName === "dark" ? "#FFFFFF" : "#111827")
                                                    : (themeName === "dark"
                                                        ? "rgba(255, 255, 255, 0.82)"
                                                        : "rgba(17, 24, 39, 0.72)"),
                                            },
                                        ]}
                                        adjustsFontSizeToFit
                                        minimumFontScale={0.82}
                                        numberOfLines={1}
                                    >
                                        {tab.label}
                                    </Text>
                                </Pressable>
                            )
                        })}
                    </View>
                    {activeInfoTabLayout ? (
                        <Animated.View
                            pointerEvents="none"
                            style={[
                                productScreenStyle.infoTabIndicator,
                                {
                                    transform: [{ translateX: infoTabIndicatorX }],
                                    width: infoTabIndicatorWidth,
                                    backgroundColor: accentPalette.primary,
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
