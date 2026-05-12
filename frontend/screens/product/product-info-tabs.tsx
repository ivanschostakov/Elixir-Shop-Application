import * as ImagePicker from "expo-image-picker"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Animated, Easing, Image, Pressable, Text, TextInput, View } from "react-native"
import type { LayoutChangeEvent } from "react-native"
import { Path, Svg } from "react-native-svg"

import { HtmlContent, hasRenderableHtmlContent } from "@/components/content/html-content"
import {
    REVIEW_STAR_PATH,
} from "@/screens/product/product-screen.constants"
import { productScreenStyle } from "@/screens/product/product-screen.styles"
import type { ProductInfoTabKey } from "@/screens/product/product-screen.types"
import type { ProductInfoTabsProps } from "@/screens/product/product-info-tabs.types"
import { useTheme } from "@/providers/theme-provider"
import type { UploadableReviewAttachment } from "@/types/product"

const INFO_TAB_INDICATOR_ANIMATION_MS = 220

type InfoTabLayout = {
    width: number
    x: number
}

function StarRating({
    rating,
    size = 16,
}: {
    rating: number
    size?: number
}) {
    const clampedRating = Math.max(0, Math.min(5, rating))

    return (
        <View style={productScreenStyle.ratingStarsRow}>
            {[0, 1, 2, 3, 4].map((index) => {
                const fill = Math.max(0, Math.min(1, clampedRating - index))
                const filledWidth = size * fill

                return (
                    <View key={index} style={[productScreenStyle.ratingStarSlot, { height: size, width: size }]}>
                        <Svg width={size} height={size} viewBox="0 0 24 24">
                            <Path d={REVIEW_STAR_PATH} fill="#D1D5DB" />
                        </Svg>
                        <View style={[productScreenStyle.ratingStarFillOverlay, { width: filledWidth }]}>
                            <Svg width={size} height={size} viewBox="0 0 24 24">
                                <Path d={REVIEW_STAR_PATH} fill="#FFC83D" />
                            </Svg>
                        </View>
                    </View>
                )
            })}
        </View>
    )
}

export function ProductInfoTabs({
    activeInfoTab,
    onChangeTab,
    onCopySku,
    onSubmitReview,
    product,
    reviewEligibilityLoading,
    reviews,
    reviewsCanSubmit,
    reviewsError,
    reviewsLoading,
    reviewsSubmitting,
    t,
}: ProductInfoTabsProps) {
    const { accentPalette, themeName } = useTheme()
    const detailsFallback = t("product.detailsNotProvided")
    const overviewHtml = hasRenderableHtmlContent(product.description) ? product.description : null
    const usageHtml = hasRenderableHtmlContent(product.usage) ? product.usage : null
    const expirationHtml = hasRenderableHtmlContent(product.expiration) ? product.expiration : null
    const productSku = product.sku?.trim() || null
    const reviewCount = reviews.length
    const reviewRatingValue =
        reviewCount > 0
            ? reviews.reduce((total, review) => total + review.value, 0) / reviewCount
            : 0
    const reviewRating = reviewRatingValue.toFixed(1)
    const [draftReviewValue, setDraftReviewValue] = useState(5)
    const [draftReviewText, setDraftReviewText] = useState("")
    const [draftReviewAttachments, setDraftReviewAttachments] = useState<UploadableReviewAttachment[]>([])
    const [submitError, setSubmitError] = useState<string | null>(null)
    const [infoTabLayouts, setInfoTabLayouts] = useState<Partial<Record<ProductInfoTabKey, InfoTabLayout>>>({})
    const infoTabIndicatorX = useRef(new Animated.Value(0)).current
    const infoTabIndicatorWidth = useRef(new Animated.Value(0)).current
    const hasMountedInfoTabIndicator = useRef(false)
    const infoTabs = useMemo(
        () => [
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
            {
                key: "reviews" as const,
                label: `${t("product.tabReviews")} (${reviewCount})`,
            },
        ],
        [reviewCount, t],
    )
    const activeInfoTabLayout = infoTabLayouts[activeInfoTab]

    const handleInfoTabLayout = useCallback((tabKey: ProductInfoTabKey, event: LayoutChangeEvent) => {
        const { width, x } = event.nativeEvent.layout

        setInfoTabLayouts((currentLayouts) => {
            const existingLayout = currentLayouts[tabKey]

            if (existingLayout && existingLayout.width === width && existingLayout.x === x) {
                return currentLayouts
            }

            return {
                ...currentLayouts,
                [tabKey]: { width, x },
            }
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
                    <StarRating rating={reviewRatingValue} size={16} />
                    <Text style={productScreenStyle.reviewsSummaryValue}>{reviewRating}</Text>
                </View>
                <Text style={productScreenStyle.reviewWriteLabel}>{t("product.writeReview")}</Text>
                {reviewEligibilityLoading ? (
                    <Text style={productScreenStyle.detailRichText}>{t("product.reviewEligibilityLoading")}</Text>
                ) : null}
                {!reviewEligibilityLoading && !reviewsCanSubmit ? (
                    <Text style={productScreenStyle.detailRichText}>{t("product.reviewRequiresPurchase")}</Text>
                ) : null}
                {!reviewEligibilityLoading && reviewsCanSubmit ? (
                    <View style={productScreenStyle.reviewComposer}>
                        <View style={productScreenStyle.reviewRatingOptionsRow}>
                            {[1, 2, 3, 4, 5].map((rating) => {
                                const isActive = draftReviewValue === rating

                                return (
                                    <Pressable
                                        key={rating}
                                        accessibilityRole="button"
                                        accessibilityState={{ selected: isActive, disabled: reviewsSubmitting }}
                                        disabled={reviewsSubmitting}
                                        onPress={() => {
                                            setDraftReviewValue(rating)
                                        }}
                                        style={({ pressed }) => [
                                            productScreenStyle.reviewRatingOption,
                                            isActive && productScreenStyle.reviewRatingOptionActive,
                                            isActive && {
                                                backgroundColor: accentPalette.primary,
                                                borderColor: accentPalette.primary,
                                            },
                                            pressed && productScreenStyle.reviewRatingOptionPressed,
                                        ]}
                                    >
                                        <Text
                                            style={[
                                                productScreenStyle.reviewRatingOptionText,
                                                isActive && productScreenStyle.reviewRatingOptionTextActive,
                                                isActive && { color: accentPalette.onPrimary },
                                            ]}
                                        >
                                            {rating}
                                        </Text>
                                    </Pressable>
                                )
                            })}
                        </View>
                        <TextInput
                            editable={!reviewsSubmitting}
                            maxLength={1000}
                            multiline
                            onChangeText={setDraftReviewText}
                            placeholder={t("product.reviewTextPlaceholder")}
                            style={productScreenStyle.reviewComposerInput}
                            value={draftReviewText}
                        />
                        <Pressable
                            accessibilityRole="button"
                            disabled={reviewsSubmitting}
                            onPress={() => {
                                setSubmitError(null)
                                void onSubmitReview(
                                    draftReviewValue,
                                    draftReviewText.trim() || null,
                                    draftReviewAttachments,
                                )
                                    .then(() => {
                                        setDraftReviewText("")
                                        setDraftReviewValue(5)
                                        setDraftReviewAttachments([])
                                    })
                                    .catch((error: unknown) => {
                                        setSubmitError(error instanceof Error ? error.message : t("product.reviewSubmitFailed"))
                                    })
                            }}
                            style={({ pressed }) => [
                                productScreenStyle.reviewSubmitButton,
                                { backgroundColor: accentPalette.primary },
                                reviewsSubmitting && productScreenStyle.reviewSubmitButtonDisabled,
                                pressed && { backgroundColor: accentPalette.primaryPressed },
                            ]}
                        >
                            <Text style={[productScreenStyle.reviewSubmitButtonText, { color: accentPalette.onPrimary }]}>
                                {reviewsSubmitting ? t("product.reviewSubmitLoading") : t("product.reviewSubmit")}
                            </Text>
                        </Pressable>
                        <Pressable
                            accessibilityRole="button"
                            disabled={reviewsSubmitting}
                            onPress={() => {
                                void (async () => {
                                    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync()
                                    if (!permission.granted) {
                                        setSubmitError(t("product.reviewPhotoPermissionDenied"))
                                        return
                                    }

                                    const result = await ImagePicker.launchImageLibraryAsync({
                                        allowsMultipleSelection: true,
                                        mediaTypes: ["images"],
                                        quality: 0.9,
                                    })

                                    if (result.canceled) {
                                        return
                                    }

                                    setSubmitError(null)
                                    setDraftReviewAttachments((current) => [
                                        ...current,
                                        ...result.assets.map((asset, index) => ({
                                            uri: asset.uri,
                                            fileName: asset.fileName ?? `review-image-${Date.now()}-${index + 1}.jpg`,
                                            mimeType: asset.mimeType ?? "image/jpeg",
                                        })),
                                    ])
                                })()
                            }}
                            style={({ pressed }) => [
                                productScreenStyle.reviewPhotoButton,
                                { borderColor: accentPalette.primary, backgroundColor: accentPalette.primaryMuted },
                                reviewsSubmitting && productScreenStyle.reviewSubmitButtonDisabled,
                                pressed && productScreenStyle.reviewPhotoButtonPressed,
                            ]}
                        >
                            <Text style={[productScreenStyle.reviewPhotoButtonText, { color: accentPalette.primary }]}>
                                {t("product.reviewAddPhoto")}
                            </Text>
                        </Pressable>
                        {draftReviewAttachments.length > 0 ? (
                            <View style={productScreenStyle.reviewAttachmentPreviewRow}>
                                {draftReviewAttachments.map((attachment, attachmentIndex) => (
                                    <Pressable
                                        key={`${attachment.uri}-${attachmentIndex}`}
                                        accessibilityRole="button"
                                        onPress={() => {
                                            setDraftReviewAttachments((current) =>
                                                current.filter((_, index) => index !== attachmentIndex),
                                            )
                                        }}
                                        style={({ pressed }) => [
                                            productScreenStyle.reviewAttachmentPreviewTile,
                                            pressed && productScreenStyle.reviewPhotoButtonPressed,
                                        ]}
                                    >
                                        <Image
                                            source={{ uri: attachment.uri }}
                                            style={productScreenStyle.reviewAttachmentPreviewImage}
                                        />
                                    </Pressable>
                                ))}
                            </View>
                        ) : null}
                        {submitError ? <Text style={productScreenStyle.reviewSubmitError}>{submitError}</Text> : null}
                    </View>
                ) : null}
                {reviewsLoading ? <Text style={productScreenStyle.detailRichText}>{t("product.reviewsLoading")}</Text> : null}
                {reviewsError ? <Text style={productScreenStyle.detailRichText}>{reviewsError}</Text> : null}
                {!reviewsLoading && !reviewsError && !reviews.length ? (
                    <Text style={productScreenStyle.detailRichText}>{t("product.reviewsEmpty")}</Text>
                ) : null}
                {!reviewsLoading && !reviewsError && reviews.length
                    ? reviews.map((review) => (
                          <View key={review.id} style={productScreenStyle.reviewCard}>
                              <View style={productScreenStyle.reviewCardHeader}>
                                  <Text style={productScreenStyle.reviewCardAuthor}>
                                      @{review.author_username}
                                  </Text>
                                  <View style={productScreenStyle.reviewCardRatingRow}>
                                      <StarRating rating={review.value} size={14} />
                                      <Text style={productScreenStyle.reviewCardRating}>{review.value.toFixed(1)}</Text>
                                  </View>
                              </View>
                              <Text style={productScreenStyle.reviewCardText}>
                                  {review.text?.trim() || detailsFallback}
                              </Text>
                              {review.attachments.length ? (
                                  <View style={productScreenStyle.reviewCardAttachmentsRow}>
                                      {review.attachments.map((attachment) => (
                                          <Image
                                              key={attachment.id}
                                              source={{ uri: attachment.image_url }}
                                              style={productScreenStyle.reviewCardAttachmentImage}
                                          />
                                      ))}
                                  </View>
                              ) : null}
                          </View>
                      ))
                    : null}
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
                                        handleInfoTabLayout(tab.key, event)
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
                                            {
                                                color: isActive
                                                    ? (themeName === "dark" ? "#FFFFFF" : "#111827")
                                                    : (themeName === "dark" ? "rgba(255, 255, 255, 0.82)" : "rgba(17, 24, 39, 0.72)"),
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
