import { useEffect, useRef, useState } from "react"
import { Alert, Image, Pressable, ScrollView, Text, TextInput, View } from "react-native"
import { useRouter } from "expo-router"
import { Path, Svg } from "react-native-svg"

import {
    ORDER_DRAFT_NAME_MAX_LENGTH,
} from "@/components/content/recent-order-drafts-rail.constants"
import type {
    RecentOrderDraftCardProps,
    RecentOrderDraftsRailProps,
} from "@/components/content/recent-order-drafts-rail.types"
import {
    formatMoney,
    getDraftDescription,
    getDraftUpdateErrorMessage,
    getModeBadgeStyle,
    getPositionsLabel,
    normalizeDraftText,
} from "@/components/content/recent-order-drafts-rail.utils"
import { SectionHeader } from "@/components/content/section-header"
import { ROUTES } from "@/constants/routes"
import { useBasketMutations } from "@/hooks/basket/use-basket-mutations"
import { setSelectedDeliveryAddress } from "@/hooks/delivery/delivery-address-selection-store"
import { setSelectedDeliveryCountry } from "@/hooks/delivery/delivery-country-selection-store"
import { setSelectedDeliveryPoint } from "@/hooks/delivery/delivery-point-selection-store"
import { clearOrderDraftSnapshot, getOrderDraftSnapshot, setOrderDraftSnapshot } from "@/hooks/order-draft/order-draft-store"
import { getOrderDraftTitle } from "@/hooks/order-draft/order-draft.utils"
import { useLanguage } from "@/providers/language-provider"
import { getBasketErrorMessage } from "@/screens/cart/cart-screen.utils"
import { deleteOrderDraft, updateOrderDraft } from "@/services/api/order-drafts"
import { colors } from "@/theme/colors"
import { recentOrderDraftsRailStyles } from "./recent-order-drafts-rail.styles"

function RecentOrderDraftCard({ draft, onDraftUpdated, onDraftDeleted }: RecentOrderDraftCardProps) {
    const router = useRouter()
    const { t } = useLanguage()
    const draftTitleInputRef = useRef<TextInput | null>(null)
    const { error: basketError, restoreDraft, updating: isRestoringDraft } = useBasketMutations()
    const [draftNameInput, setDraftNameInput] = useState(draft.draft_name ?? "")
    const [isEditingTitle, setIsEditingTitle] = useState(false)
    const [isSavingTitle, setIsSavingTitle] = useState(false)
    const [isDeletingDraft, setIsDeletingDraft] = useState(false)

    const visibleItems = draft.items.slice(0, 4)
    const totalLabel = formatMoney(Number(draft.grand_total), draft.currency)
    const ctaLabel = totalLabel ?? "Оформить"
    const draftTitle = getOrderDraftTitle(draft)
    const draftDescription = getDraftDescription(draft)
    const titlePlaceholder = getOrderDraftTitle({
        ...draft,
        draft_name: null,
    })
    const normalizedDraftName = normalizeDraftText(draftNameInput)
    const hasDraftTitleChanges = normalizedDraftName !== draft.draft_name

    useEffect(() => {
        setDraftNameInput(draft.draft_name ?? "")
        setIsEditingTitle(false)
    }, [draft.draft_name, draft.id])

    const handleOpenDraft = () => {
        if (isEditingTitle) {
            draftTitleInputRef.current?.blur()
            return
        }

        router.push(`${ROUTES.checkout}?draftId=${draft.id}`)
    }

    const handleSaveDraftTitle = async () => {
        if (!hasDraftTitleChanges || isSavingTitle) {
            return
        }

        setIsSavingTitle(true)

        try {
            const updatedDraft = await updateOrderDraft(draft.id, {
                draft_name: normalizedDraftName,
            })
            onDraftUpdated(updatedDraft)
            setOrderDraftSnapshot(updatedDraft)
        } catch (saveError) {
            Alert.alert(getDraftUpdateErrorMessage(saveError, t("checkout.saveDraftMetaFailed")))
        } finally {
            setIsSavingTitle(false)
        }
    }

    const handleRestoreDraft = async () => {
        draftTitleInputRef.current?.blur()

        try {
            await restoreDraft(draft.id)
            setOrderDraftSnapshot(draft)
            setSelectedDeliveryCountry(draft.delivery_address?.country_code ?? null)
            setSelectedDeliveryAddress(null)
            setSelectedDeliveryPoint(null)
            router.push(`${ROUTES.checkout}?draftId=${draft.id}`)
        } catch (restoreError) {
            Alert.alert(getBasketErrorMessage(restoreError, basketError, t))
        }
    }

    const handleDeleteDraft = async () => {
        if (isDeletingDraft) {
            return
        }

        setIsDeletingDraft(true)

        try {
            await deleteOrderDraft(draft.id)
            if (getOrderDraftSnapshot()?.id === draft.id) {
                clearOrderDraftSnapshot()
            }
            onDraftDeleted(draft.id)
        } catch (deleteError) {
            Alert.alert(getDraftUpdateErrorMessage(deleteError, t("cart.recentDraftsDeleteFailed")))
        } finally {
            setIsDeletingDraft(false)
        }
    }

    const handleConfirmDeleteDraft = () => {
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
                        void handleDeleteDraft()
                    },
                },
            ],
        )
    }

    return (
        <Pressable
            accessibilityLabel={`${t("cart.recentDraftsOpenDraft")}: ${draftTitle}`}
            accessibilityRole="button"
            onPress={handleOpenDraft}
            style={({ pressed }) => [
                recentOrderDraftsRailStyles.card,
                pressed && !isEditingTitle && recentOrderDraftsRailStyles.cardPressed,
            ]}
        >
            <Pressable
                accessibilityLabel={t("cart.recentDraftsDeleteAction")}
                accessibilityRole="button"
                disabled={isDeletingDraft}
                hitSlop={10}
                onPress={(event) => {
                    event.stopPropagation()
                    handleConfirmDeleteDraft()
                }}
                style={({ pressed }) => [
                    recentOrderDraftsRailStyles.cardDeleteBadge,
                    isDeletingDraft && recentOrderDraftsRailStyles.cardDeleteBadgeDisabled,
                    pressed && recentOrderDraftsRailStyles.cardDeleteBadgePressed,
                ]}
            >
                <Svg width={16} height={16} viewBox="0 0 24 24" fill="none">
                    <Path
                        d="M4 6H20L18.4199 20.2209C18.3074 21.2337 17.4512 22 16.4321 22H7.56786C6.54876 22 5.69264 21.2337 5.5801 20.2209L4 6Z"
                        stroke={colors.text}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                    />
                    <Path
                        d="M7.34491 3.14716C7.67506 2.44685 8.37973 2 9.15396 2H14.846C15.6203 2 16.3249 2.44685 16.6551 3.14716L18 6H6L7.34491 3.14716Z"
                        stroke={colors.text}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                    />
                    <Path
                        d="M2 6H22"
                        stroke={colors.text}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                    />
                    <Path
                        d="M10 11V16"
                        stroke={colors.text}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                    />
                    <Path
                        d="M14 11V16"
                        stroke={colors.text}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                    />
                </Svg>
            </Pressable>

            <View style={recentOrderDraftsRailStyles.collage}>
                {visibleItems.map((item, index) => {
                    return (
                        <View
                            key={`${draft.id}-${item.id}`}
                            style={[
                                recentOrderDraftsRailStyles.collageTile,
                                getModeBadgeStyle(visibleItems.length, index),
                            ]}
                        >
                            <Image
                                source={{ uri: item.image_url }}
                                style={recentOrderDraftsRailStyles.collageTileImage}
                                resizeMode="cover"
                            />
                        </View>
                    )
                })}
            </View>

            <View style={recentOrderDraftsRailStyles.cardBody}>
                {isEditingTitle ? (
                    <TextInput
                        autoCapitalize="sentences"
                        autoFocus
                        maxLength={ORDER_DRAFT_NAME_MAX_LENGTH}
                        onBlur={() => {
                            setIsEditingTitle(false)
                            void handleSaveDraftTitle()
                        }}
                        onChangeText={setDraftNameInput}
                        onSubmitEditing={() => {
                            setIsEditingTitle(false)
                            void handleSaveDraftTitle()
                        }}
                        placeholder={titlePlaceholder}
                        placeholderTextColor="#9CA3AF"
                        ref={draftTitleInputRef}
                        returnKeyType="done"
                        style={[
                            recentOrderDraftsRailStyles.cardTitleInput,
                            isSavingTitle && recentOrderDraftsRailStyles.cardTitleInputSaving,
                        ]}
                        value={draftNameInput}
                    />
                ) : (
                    <Pressable
                        accessibilityLabel={t("checkout.editDraftTitle")}
                        accessibilityRole="button"
                        disabled={isSavingTitle}
                        onPress={(event) => {
                            event.stopPropagation()
                            setIsEditingTitle(true)
                        }}
                        style={({ pressed }) => [
                            recentOrderDraftsRailStyles.cardTitleButton,
                            isSavingTitle && recentOrderDraftsRailStyles.cardTitleButtonDisabled,
                            pressed && recentOrderDraftsRailStyles.cardTitleButtonPressed,
                        ]}
                    >
                        <Text numberOfLines={1} style={recentOrderDraftsRailStyles.cardTitle}>
                            {draftTitle}
                        </Text>
                    </Pressable>
                )}

                <Text numberOfLines={4} style={recentOrderDraftsRailStyles.cardSubtitle}>
                    {draftDescription}
                </Text>

                <View style={recentOrderDraftsRailStyles.cardFooter}>
                    <Text style={recentOrderDraftsRailStyles.cardPositions}>
                        {draft.items_count} {getPositionsLabel(draft.items_count)}
                    </Text>
                </View>

                <Pressable
                    accessibilityLabel={ctaLabel}
                    accessibilityRole="button"
                    disabled={isRestoringDraft}
                    onPress={(event) => {
                        event.stopPropagation()
                        void handleRestoreDraft()
                    }}
                    style={({ pressed }) => [
                        recentOrderDraftsRailStyles.cardCtaButton,
                        isRestoringDraft && recentOrderDraftsRailStyles.cardCtaButtonDisabled,
                        pressed && recentOrderDraftsRailStyles.cardCtaButtonPressed,
                    ]}
                >
                    <Text style={recentOrderDraftsRailStyles.cardCtaButtonText}>{ctaLabel}</Text>
                </Pressable>
            </View>
        </Pressable>
    )
}

export function RecentOrderDraftsRail({ drafts }: RecentOrderDraftsRailProps) {
    const { t } = useLanguage()
    const [localDrafts, setLocalDrafts] = useState(drafts)

    useEffect(() => {
        setLocalDrafts(drafts)
    }, [drafts])

    if (!localDrafts.length) {
        return null
    }

    return (
        <View style={recentOrderDraftsRailStyles.section}>
            <SectionHeader
                title={t("cart.recentDraftsTitle")}
                eyebrow={t("cart.recentDraftsEyebrow")}
                description={t("cart.recentDraftsDescription")}
            />

            <ScrollView
                horizontal
                contentContainerStyle={recentOrderDraftsRailStyles.scrollContent}
                showsHorizontalScrollIndicator={false}
                style={recentOrderDraftsRailStyles.scrollView}
            >
                {localDrafts.map((draft) => (
                    <RecentOrderDraftCard
                        key={draft.id}
                        draft={draft}
                        onDraftDeleted={(draftId) => {
                            setLocalDrafts((currentDrafts) =>
                                currentDrafts.filter((currentDraft) => currentDraft.id !== draftId)
                            )
                        }}
                        onDraftUpdated={(updatedDraft) => {
                            setLocalDrafts((currentDrafts) =>
                                currentDrafts.map((currentDraft) =>
                                    currentDraft.id === updatedDraft.id ? updatedDraft : currentDraft
                                )
                            )
                        }}
                    />
                ))}
            </ScrollView>
        </View>
    )
}
