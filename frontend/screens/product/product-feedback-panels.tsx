import * as ImagePicker from "expo-image-picker"
import { useState } from "react"
import { Image, Pressable, Switch, Text, TextInput, View } from "react-native"
import { Path, Svg } from "react-native-svg"

import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useTheme } from "@/providers/theme-provider"
import { REVIEW_STAR_PATH } from "@/screens/product/product-screen.constants"
import { createProductScreenStyle } from "@/screens/product/product-screen.styles"
import type { ProductFeedbackPanelKey } from "@/screens/product/product-screen.types"
import type { TranslationFn } from "@/providers/language-provider.types"
import type {
    ProductQuestionRead,
    ProductReviewRead,
    UploadableReviewAttachment,
} from "@/types/product"

type ProductFeedbackPanelsProps = {
    activePanel: ProductFeedbackPanelKey | null
    onChangePanel: (panel: ProductFeedbackPanelKey) => void
    onSubmitQuestion: (text: string) => Promise<void>
    onSubmitReview: (
        value: number,
        text: string | null,
        attachments: UploadableReviewAttachment[],
        hideSenderName: boolean,
    ) => Promise<void>
    questionError: string | null
    questionLoading: boolean
    questionSubmitting: boolean
    questionTotalCount: number
    questions: ProductQuestionRead[]
    reviewEligibilityLoading: boolean
    reviews: ProductReviewRead[]
    reviewsCanSubmit: boolean
    reviewsError: string | null
    reviewsLoading: boolean
    reviewsSubmitting: boolean
    reviewRatingAverage: number
    reviewTotalCount: number
    t: TranslationFn
}

function StarRating({ rating, size = 16 }: { rating: number; size?: number }) {
    const productScreenStyle = useThemeStyles(createProductScreenStyle)
    const clampedRating = Math.max(0, Math.min(5, rating))

    return (
        <View style={productScreenStyle.ratingStarsRow}>
            {[0, 1, 2, 3, 4].map((index) => {
                const fill = Math.max(0, Math.min(1, clampedRating - index))
                return (
                    <View key={index} style={[productScreenStyle.ratingStarSlot, { height: size, width: size }]}>
                        <Svg width={size} height={size} viewBox="0 0 24 24">
                            <Path d={REVIEW_STAR_PATH} fill="#D1D5DB" />
                        </Svg>
                        <View style={[productScreenStyle.ratingStarFillOverlay, { width: size * fill }]}>
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

export function ProductFeedbackPanels({
    activePanel,
    onChangePanel,
    onSubmitQuestion,
    onSubmitReview,
    questionError,
    questionLoading,
    questionSubmitting,
    questionTotalCount,
    questions,
    reviewEligibilityLoading,
    reviews,
    reviewsCanSubmit,
    reviewsError,
    reviewsLoading,
    reviewsSubmitting,
    reviewRatingAverage,
    reviewTotalCount,
    t,
}: ProductFeedbackPanelsProps) {
    const productScreenStyle = useThemeStyles(createProductScreenStyle)
    const { accentPalette, palette } = useTheme()
    const [draftReviewValue, setDraftReviewValue] = useState(5)
    const [draftReviewText, setDraftReviewText] = useState("")
    const [draftReviewAttachments, setDraftReviewAttachments] = useState<UploadableReviewAttachment[]>([])
    const [hideSenderName, setHideSenderName] = useState(false)
    const [reviewSubmitError, setReviewSubmitError] = useState<string | null>(null)
    const [reviewSubmitSuccess, setReviewSubmitSuccess] = useState(false)
    const [draftQuestionText, setDraftQuestionText] = useState("")
    const [questionSubmitError, setQuestionSubmitError] = useState<string | null>(null)
    const [questionSubmitSuccess, setQuestionSubmitSuccess] = useState(false)

    const renderReviewPanel = () => (
        <View style={productScreenStyle.feedbackExpandedCard}>
            <Text style={productScreenStyle.feedbackPanelTitle}>{t("product.reviewsTitle")}</Text>
            <Text style={productScreenStyle.reviewWriteLabel}>{t("product.writeReview")}</Text>
            {reviewEligibilityLoading ? (
                <Text style={productScreenStyle.detailRichText}>{t("product.reviewEligibilityLoading")}</Text>
            ) : null}
            {!reviewEligibilityLoading && !reviewsCanSubmit ? (
                <Text style={productScreenStyle.detailRichText}>{t("product.reviewRequiresPurchase")}</Text>
            ) : null}
            {!reviewEligibilityLoading && reviewsCanSubmit ? (
                <View style={productScreenStyle.reviewComposer}>
                    <Text style={productScreenStyle.composerFieldLabel}>{t("product.reviewChooseRating")}</Text>
                    <View style={productScreenStyle.reviewStarPickerRow}>
                        {[1, 2, 3, 4, 5].map((rating) => (
                            <Pressable
                                key={rating}
                                accessibilityLabel={`${rating}`}
                                accessibilityRole="button"
                                accessibilityState={{
                                    selected: draftReviewValue === rating,
                                    disabled: reviewsSubmitting,
                                }}
                                disabled={reviewsSubmitting}
                                onPress={() => setDraftReviewValue(rating)}
                                style={({ pressed }) => [
                                    productScreenStyle.reviewStarPickerButton,
                                    pressed && productScreenStyle.reviewRatingOptionPressed,
                                ]}
                            >
                                <Svg width={34} height={34} viewBox="0 0 24 24">
                                    <Path
                                        d={REVIEW_STAR_PATH}
                                        fill={rating <= draftReviewValue ? "#FFC83D" : palette.border}
                                    />
                                </Svg>
                            </Pressable>
                        ))}
                    </View>
                    <TextInput
                        editable={!reviewsSubmitting}
                        maxLength={1000}
                        multiline
                        onChangeText={setDraftReviewText}
                        placeholder={t("product.reviewTextPlaceholder")}
                        placeholderTextColor={palette.mutedText}
                        style={productScreenStyle.reviewComposerInput}
                        value={draftReviewText}
                    />
                    <View style={productScreenStyle.reviewAnonymousRow}>
                        <View style={productScreenStyle.reviewAnonymousCopy}>
                            <Text style={productScreenStyle.reviewAnonymousTitle}>{t("product.reviewHideName")}</Text>
                            <Text style={productScreenStyle.reviewAnonymousHint}>{t("product.reviewHideNameHint")}</Text>
                        </View>
                        <Switch
                            accessibilityLabel={t("product.reviewHideName")}
                            disabled={reviewsSubmitting}
                            onValueChange={setHideSenderName}
                            thumbColor={hideSenderName ? accentPalette.onPrimary : palette.surface}
                            trackColor={{
                                false: palette.border,
                                true: accentPalette.primary,
                            }}
                            value={hideSenderName}
                        />
                    </View>
                    <View style={productScreenStyle.reviewComposerActions}>
                        <Pressable
                            accessibilityRole="button"
                            disabled={reviewsSubmitting}
                            onPress={() => {
                                setReviewSubmitError(null)
                                setReviewSubmitSuccess(false)
                                void onSubmitReview(
                                    draftReviewValue,
                                    draftReviewText.trim() || null,
                                    draftReviewAttachments,
                                    hideSenderName,
                                )
                                    .then(() => {
                                        setDraftReviewText("")
                                        setDraftReviewValue(5)
                                        setDraftReviewAttachments([])
                                        setHideSenderName(false)
                                        setReviewSubmitSuccess(true)
                                    })
                                    .catch((error: unknown) => {
                                        setReviewSubmitError(
                                            error instanceof Error
                                                ? error.message
                                                : t("product.reviewSubmitFailed"),
                                        )
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
                                    const result = await ImagePicker.launchImageLibraryAsync({
                                        allowsMultipleSelection: true,
                                        mediaTypes: ["images"],
                                        quality: 0.9,
                                    })
                                    if (result.canceled) {
                                        return
                                    }
                                    setReviewSubmitError(null)
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
                                {
                                    borderColor: accentPalette.primary,
                                    backgroundColor: accentPalette.primaryMuted,
                                },
                                reviewsSubmitting && productScreenStyle.reviewSubmitButtonDisabled,
                                pressed && productScreenStyle.reviewPhotoButtonPressed,
                            ]}
                        >
                            <Text style={[productScreenStyle.reviewPhotoButtonText, { color: accentPalette.primary }]}>
                                {t("product.reviewAddPhoto")}
                            </Text>
                        </Pressable>
                    </View>
                    {draftReviewAttachments.length ? (
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
                    {reviewSubmitError ? (
                        <Text style={productScreenStyle.reviewSubmitError}>{reviewSubmitError}</Text>
                    ) : null}
                    {reviewSubmitSuccess ? (
                        <Text style={productScreenStyle.detailRichText}>{t("product.reviewModerationNotice")}</Text>
                    ) : null}
                </View>
            ) : null}
            {reviewsLoading ? <Text style={productScreenStyle.detailRichText}>{t("product.reviewsLoading")}</Text> : null}
            {reviewsError ? <Text style={productScreenStyle.detailRichText}>{reviewsError}</Text> : null}
            {!reviewsLoading && !reviewsError && !reviews.length ? (
                <Text style={productScreenStyle.detailRichText}>{t("product.reviewsEmpty")}</Text>
            ) : null}
            {!reviewsLoading && !reviewsError
                ? reviews.map((review) => (
                    <View key={review.id} style={productScreenStyle.reviewCard}>
                        <View style={productScreenStyle.reviewCardHeader}>
                            <Text style={productScreenStyle.reviewCardAuthor}>
                                {review.is_anonymous
                                    ? t("product.reviewAnonymousAuthor")
                                    : review.author_username}
                            </Text>
                            <View style={productScreenStyle.reviewCardRatingRow}>
                                <StarRating rating={review.value} size={14} />
                                <Text style={productScreenStyle.reviewCardRating}>{review.value.toFixed(1)}</Text>
                            </View>
                        </View>
                        <Text style={productScreenStyle.reviewCardText}>
                            {review.text?.trim() || t("product.detailsNotProvided")}
                        </Text>
                        {review.answer ? (
                            <View style={productScreenStyle.feedbackAnswer}>
                                <Text style={productScreenStyle.feedbackAnswerLabel}>{t("product.storeAnswer")}</Text>
                                <Text style={productScreenStyle.reviewCardText}>{review.answer}</Text>
                            </View>
                        ) : null}
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

    const renderQuestionPanel = () => (
        <View style={productScreenStyle.feedbackExpandedCard}>
            <Text style={productScreenStyle.feedbackPanelTitle}>{t("product.questionsTitle")}</Text>
            <Text style={productScreenStyle.reviewWriteLabel}>{t("product.askQuestion")}</Text>
            <View style={productScreenStyle.reviewComposer}>
                <TextInput
                    editable={!questionSubmitting}
                    maxLength={2000}
                    multiline
                    onChangeText={setDraftQuestionText}
                    placeholder={t("product.questionTextPlaceholder")}
                    placeholderTextColor={palette.mutedText}
                    style={productScreenStyle.reviewComposerInput}
                    value={draftQuestionText}
                />
                <Pressable
                    accessibilityRole="button"
                    disabled={questionSubmitting || draftQuestionText.trim().length < 3}
                    onPress={() => {
                        setQuestionSubmitError(null)
                        setQuestionSubmitSuccess(false)
                        void onSubmitQuestion(draftQuestionText.trim())
                            .then(() => {
                                setDraftQuestionText("")
                                setQuestionSubmitSuccess(true)
                            })
                            .catch((error: unknown) => {
                                setQuestionSubmitError(
                                    error instanceof Error
                                        ? error.message
                                        : t("product.questionSubmitFailed"),
                                )
                            })
                    }}
                    style={({ pressed }) => [
                        productScreenStyle.reviewSubmitButton,
                        { backgroundColor: accentPalette.primary },
                        (questionSubmitting || draftQuestionText.trim().length < 3)
                            && productScreenStyle.reviewSubmitButtonDisabled,
                        pressed && { backgroundColor: accentPalette.primaryPressed },
                    ]}
                >
                    <Text style={[productScreenStyle.reviewSubmitButtonText, { color: accentPalette.onPrimary }]}>
                        {questionSubmitting ? t("product.questionSubmitLoading") : t("product.questionSubmit")}
                    </Text>
                </Pressable>
                {questionSubmitError ? (
                    <Text style={productScreenStyle.reviewSubmitError}>{questionSubmitError}</Text>
                ) : null}
                {questionSubmitSuccess ? (
                    <Text style={productScreenStyle.detailRichText}>{t("product.questionModerationNotice")}</Text>
                ) : null}
            </View>
            {questionLoading ? (
                <Text style={productScreenStyle.detailRichText}>{t("product.questionsLoading")}</Text>
            ) : null}
            {questionError ? <Text style={productScreenStyle.detailRichText}>{questionError}</Text> : null}
            {!questionLoading && !questionError && !questions.length ? (
                <Text style={productScreenStyle.detailRichText}>{t("product.questionsEmpty")}</Text>
            ) : null}
            {!questionLoading && !questionError
                ? questions.map((question) => (
                    <View key={question.id} style={productScreenStyle.reviewCard}>
                        <Text style={productScreenStyle.reviewCardAuthor}>{question.author_username}</Text>
                        <Text style={productScreenStyle.reviewCardText}>{question.text}</Text>
                        {question.answer ? (
                            <View style={productScreenStyle.feedbackAnswer}>
                                <Text style={productScreenStyle.feedbackAnswerLabel}>{t("product.storeAnswer")}</Text>
                                <Text style={productScreenStyle.reviewCardText}>{question.answer}</Text>
                            </View>
                        ) : null}
                    </View>
                ))
                : null}
        </View>
    )

    return (
        <View style={productScreenStyle.feedbackSection}>
            <View style={productScreenStyle.feedbackSummaryRow}>
                <Pressable
                    accessibilityRole="button"
                    accessibilityState={{ selected: activePanel === "reviews" }}
                    onPress={() => onChangePanel("reviews")}
                    style={({ pressed }) => [
                        productScreenStyle.feedbackSummaryCard,
                        productScreenStyle.feedbackReviewsSummaryCard,
                        activePanel === "reviews" && {
                            borderColor: accentPalette.primary,
                            backgroundColor: accentPalette.primaryMuted,
                        },
                        pressed && productScreenStyle.feedbackSummaryCardPressed,
                    ]}
                >
                    <View style={productScreenStyle.feedbackSummaryValueRow}>
                        <StarRating rating={reviewRatingAverage} size={18} />
                        <Text style={productScreenStyle.feedbackSummaryValue}>
                            {reviewTotalCount ? reviewRatingAverage.toFixed(1) : "—"}
                        </Text>
                    </View>
                    <Text style={productScreenStyle.feedbackSummaryLabel}>
                        {reviewTotalCount} {t("product.reviewsCount")}
                    </Text>
                </Pressable>
                <Pressable
                    accessibilityRole="button"
                    accessibilityState={{ selected: activePanel === "questions" }}
                    onPress={() => onChangePanel("questions")}
                    style={({ pressed }) => [
                        productScreenStyle.feedbackSummaryCard,
                        productScreenStyle.feedbackQuestionsSummaryCard,
                        activePanel === "questions" && {
                            borderColor: accentPalette.primary,
                            backgroundColor: accentPalette.primaryMuted,
                        },
                        pressed && productScreenStyle.feedbackSummaryCardPressed,
                    ]}
                >
                    <View style={productScreenStyle.feedbackSummaryValueRow}>
                        <View style={[productScreenStyle.questionIcon, { backgroundColor: accentPalette.primaryMuted }]}>
                            <Text style={[productScreenStyle.questionIconText, { color: accentPalette.primary }]}>?</Text>
                        </View>
                        <Text style={productScreenStyle.feedbackSummaryValue}>{questionTotalCount}</Text>
                    </View>
                    <Text style={productScreenStyle.feedbackSummaryLabel}>{t("product.questionsCount")}</Text>
                </Pressable>
            </View>
            {activePanel === "reviews" ? renderReviewPanel() : null}
            {activePanel === "questions" ? renderQuestionPanel() : null}
        </View>
    )
}
