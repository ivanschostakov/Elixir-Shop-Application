import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
    ActivityIndicator,
    Alert,
    FlatList,
    Image,
    Platform,
    Pressable,
    Text,
    View,
    useWindowDimensions,
} from "react-native"
import { router } from "expo-router"
import LottieView from "lottie-react-native"
import { Path, Svg } from "react-native-svg"

import { EmptyState } from "@/components/content/empty-state"
import {
    getDraftDescription,
    getModeBadgeStyle,
    formatMoney,
    getDraftUpdateErrorMessage,
} from "@/components/content/recent-order-drafts-rail.utils"
import { createContentStyles } from "@/components/content/content.styles"
import { CatalogTemplate } from "@/components/templates/catalog-template"
import { ROUTES } from "@/constants/routes"
import { STICKERS } from "@/constants/stickers"
import { clearOrderDraftSnapshot, getOrderDraftSnapshot } from "@/hooks/order-draft/order-draft-store"
import { getOrderDraftTitle } from "@/hooks/order-draft/order-draft.utils"
import { usePaginatedData } from "@/hooks/shared/use-paginated-data"
import { useLanguage } from "@/providers/language-provider"
import { deleteOrderDraft, getOrderDrafts } from "@/services/api/order-drafts"
import type { GetOrderDraftsQuery, OrderDraftRead } from "@/services/api/order-drafts.types"
import { DateRangeSheetField } from "./profile-history-screen"
import { createProfileHistoryScreenStyles } from "./profile-history-screen.styles"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useTheme } from "@/providers/theme-provider"
import {
    buildDateQueryValue,
    formatDateRangeTriggerValue,
    formatHistoryDate,
} from "./profile-history-screen.utils"

const PAGE_SIZE = 10
const EMPTY_FILTERS = {
    createdFrom: null,
    createdTo: null,
}

type ProfileDraftFilters = {
    createdFrom: string | null
    createdTo: string | null
}

function buildDraftsQuery(filters: ProfileDraftFilters, limit: number, offset: number): GetOrderDraftsQuery {
    return {
        limit,
        offset,
        created_from: buildDateQueryValue(filters.createdFrom),
        created_to: buildDateQueryValue(filters.createdTo, true),
    }
}

function DraftHistoryCard({ draft, onDraftDeleted }: { draft: OrderDraftRead, onDraftDeleted: (draftId: number) => void }) {
    const profileHistoryScreenStyles = useThemeStyles(createProfileHistoryScreenStyles)
    const { t } = useLanguage()
    const title = getOrderDraftTitle(draft)
    const subtitle = draft.delivery_address?.full_address || getDraftDescription(draft)
    const totalLabel = formatMoney(Number(draft.grand_total), draft.currency) ?? draft.grand_total
    const visibleItems = draft.items.slice(0, 4)
    const [isDeleting, setIsDeleting] = useState(false)

    const handleDeleteDraft = async () => {
        if (isDeleting) {
            return
        }

        setIsDeleting(true)
        try {
            await deleteOrderDraft(draft.id)
            if (getOrderDraftSnapshot()?.id === draft.id) {
                clearOrderDraftSnapshot()
            }
            onDraftDeleted(draft.id)
        } catch (deleteError) {
            Alert.alert(getDraftUpdateErrorMessage(deleteError, t("cart.recentDraftsDeleteFailed")))
        } finally {
            setIsDeleting(false)
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
            accessibilityLabel={title}
            accessibilityRole="button"
            onPress={() => {
                router.push({ pathname: ROUTES.checkout, params: { draftId: String(draft.id) } })
            }}
            style={({ pressed }) => [
                profileHistoryScreenStyles.historyCard,
                pressed && profileHistoryScreenStyles.historyCardPressed,
            ]}
        >
            <Pressable
                accessibilityLabel={t("cart.recentDraftsDeleteAction")}
                accessibilityRole="button"
                disabled={isDeleting}
                hitSlop={10}
                onPress={(event) => {
                    event.stopPropagation()
                    handleConfirmDeleteDraft()
                }}
                style={({ pressed }) => [
                    profileHistoryScreenStyles.historyCardDeleteBadge,
                    isDeleting && profileHistoryScreenStyles.historyCardDeleteBadgeDisabled,
                    pressed && profileHistoryScreenStyles.historyCardDeleteBadgePressed,
                ]}
            >
                <Svg width={16} height={16} viewBox="0 0 24 24" fill="none">
                    <Path
                        d="M6 6L18 18"
                        stroke="#E11D48"
                        strokeLinecap="round"
                        strokeWidth={3.4}
                    />
                    <Path
                        d="M18 6L6 18"
                        stroke="#E11D48"
                        strokeLinecap="round"
                        strokeWidth={3.4}
                    />
                </Svg>
            </Pressable>

            <View style={profileHistoryScreenStyles.historyCardCollage}>
                {visibleItems.map((item, index) => (
                    <View
                        key={`${draft.id}-${item.id}-${item.variant_id}`}
                        style={[
                            profileHistoryScreenStyles.historyCardCollageTile,
                            getModeBadgeStyle(visibleItems.length, index),
                        ]}
                    >
                        <Image
                            resizeMode="cover"
                            source={{ uri: item.image_url }}
                            style={profileHistoryScreenStyles.historyCardCollageTileImage}
                        />
                    </View>
                ))}
            </View>

            <View style={profileHistoryScreenStyles.historyCardHeader}>
                <View style={profileHistoryScreenStyles.historyCardCopy}>
                    <Text style={profileHistoryScreenStyles.historyCardEyebrow}>{t("profile.drafts.title")}</Text>
                    <Text style={profileHistoryScreenStyles.historyCardTitle}>{title}</Text>
                    {subtitle ? (
                        <Text numberOfLines={2} style={profileHistoryScreenStyles.historyCardSubtitle}>
                            {subtitle}
                        </Text>
                    ) : null}
                </View>
            </View>

            <View style={profileHistoryScreenStyles.historyCardMetaGrid}>
                <View style={profileHistoryScreenStyles.historyCardMetaRow}>
                    <Text style={profileHistoryScreenStyles.historyCardMetaLabel}>{t("profile.drafts.createdAt")}</Text>
                    <Text style={profileHistoryScreenStyles.historyCardMetaValue}>
                        {formatHistoryDate(draft.created_at)}
                    </Text>
                </View>

                <View style={profileHistoryScreenStyles.historyCardMetaRow}>
                    <Text style={profileHistoryScreenStyles.historyCardMetaLabel}>{t("profile.drafts.updatedAt")}</Text>
                    <Text style={profileHistoryScreenStyles.historyCardMetaValue}>
                        {formatHistoryDate(draft.updated_at)}
                    </Text>
                </View>

                <View style={profileHistoryScreenStyles.historyCardMetaRow}>
                    <Text style={profileHistoryScreenStyles.historyCardMetaLabel}>{t("profile.drafts.positions")}</Text>
                    <Text style={profileHistoryScreenStyles.historyCardMetaValue}>{draft.items_count}</Text>
                </View>
            </View>

            <View style={profileHistoryScreenStyles.historyCardDivider} />

            <View style={profileHistoryScreenStyles.historyCardFooter}>
                <Text style={profileHistoryScreenStyles.historyCardFooterLabel}>{t("checkout.grandTotalLabel")}</Text>
                <Text style={profileHistoryScreenStyles.historyCardFooterValue}>{totalLabel}</Text>
            </View>
        </Pressable>
    )
}

export default function ProfileDraftsScreen() {
    const contentStyles = useThemeStyles(createContentStyles)
    const profileHistoryScreenStyles = useThemeStyles(createProfileHistoryScreenStyles)
    const { palette } = useTheme()
    const { t } = useLanguage()
    const { width: windowWidth } = useWindowDimensions()
    const emptyDraftsSticker = STICKERS.orderHistoryEmpty || STICKERS.favoritesEmpty
    const listRef = useRef<FlatList<OrderDraftRead> | null>(null)
    const [filters, setFilters] = useState<ProfileDraftFilters>(EMPTY_FILTERS)
    const [deletedDraftIds, setDeletedDraftIds] = useState<number[]>([])
    const isWeb = Platform.OS === "web"
    const isDesktop = isWeb && windowWidth >= 1100
    const isTablet = isWeb && windowWidth >= 760
    const maxContentWidth = isDesktop ? 1180 : isTablet ? 960 : undefined
    const selectedDateRangeLabel = formatDateRangeTriggerValue(
        filters.createdFrom,
        filters.createdTo,
        t("profile.history.dateRangeEmpty"),
    )
    const hasActiveFilters = Boolean(filters.createdFrom || filters.createdTo)

    const { error, hasMore, items, loadMore, loading, loadingMore, reload } = usePaginatedData<OrderDraftRead>({
        deps: [filters.createdFrom, filters.createdTo],
        fetchPage: async ({ limit, offset }) => getOrderDrafts(buildDraftsQuery(filters, limit, offset)),
        getKey: (item) => String(item.id),
        pageSize: PAGE_SIZE,
    })
    const visibleDrafts = useMemo(
        () => items.filter((draft) => !deletedDraftIds.includes(draft.id)),
        [deletedDraftIds, items],
    )

    useEffect(() => {
        listRef.current?.scrollToOffset({ offset: 0, animated: false })
    }, [filters.createdFrom, filters.createdTo])

    useEffect(() => {
        setDeletedDraftIds([])
    }, [filters.createdFrom, filters.createdTo])

    const emptyStateDescription = useMemo(
        () => hasActiveFilters
            ? t("profile.drafts.searchEmptyDescription")
            : t("profile.drafts.emptyDescription"),
        [hasActiveFilters, t],
    )

    const renderItem = useCallback(
        ({ item }: { item: OrderDraftRead }) => (
            <View style={profileHistoryScreenStyles.cardWrap}>
                <DraftHistoryCard
                    draft={item}
                    onDraftDeleted={(draftId) => {
                        setDeletedDraftIds((currentIds) => [...currentIds, draftId])
                    }}
                />
            </View>
        ),
        [profileHistoryScreenStyles.cardWrap, setDeletedDraftIds],
    )

    return (
        <CatalogTemplate style={profileHistoryScreenStyles.screen}>
            <FlatList
                ref={listRef}
                contentContainerStyle={[
                    profileHistoryScreenStyles.listContent,
                    visibleDrafts.length === 0 ? profileHistoryScreenStyles.listContentEmpty : null,
                ]}
                data={visibleDrafts}
                keyExtractor={(item) => String(item.id)}
                keyboardShouldPersistTaps="handled"
                ListEmptyComponent={
                    loading ? (
                        <View style={profileHistoryScreenStyles.loaderWrap}>
                            <ActivityIndicator color={palette.primary} />
                        </View>
                    ) : error ? (
                        <EmptyState
                            eyebrow={t("profile.drafts.title")}
                            title={t("profile.drafts.loadFailedTitle")}
                            description={error}
                            actionLabel={t("common.retry")}
                            onPressAction={() => {
                                void reload()
                            }}
                        />
                    ) : (
                        <View style={profileHistoryScreenStyles.searchEmptyState}>
                            {emptyDraftsSticker.kind === "lottie" ? (
                                <LottieView
                                    autoPlay
                                    loop
                                    source={emptyDraftsSticker.source}
                                    style={profileHistoryScreenStyles.searchEmptyAnimation}
                                />
                            ) : null}

                            <Text style={profileHistoryScreenStyles.searchEmptyText}>
                                {emptyStateDescription}
                            </Text>

                            <Pressable
                                accessibilityRole="button"
                                onPress={() => {
                                    router.push(ROUTES.discover)
                                }}
                                style={({ pressed }) => pressed && profileHistoryScreenStyles.searchEmptyLinkPressed}
                            >
                                <Text style={profileHistoryScreenStyles.searchEmptyLink}>
                                    {t("profile.drafts.openCatalog")}
                                </Text>
                            </Pressable>
                        </View>
                    )
                }
                ListFooterComponent={
                    !loadingMore ? null : (
                        <View style={profileHistoryScreenStyles.footerLoaderWrap}>
                            <ActivityIndicator color={palette.primary} />
                        </View>
                    )
                }
                ListHeaderComponent={(
                    <View style={profileHistoryScreenStyles.controlsWrap}>
                        <DateRangeSheetField
                            label={t("profile.drafts.dateRangeField")}
                            labelStyle={contentStyles.browseSectionLabel}
                            onChange={(range) => {
                                setFilters({
                                    createdFrom: range.createdFrom,
                                    createdTo: range.createdTo,
                                })
                            }}
                            selectedRange={filters}
                            valueLabel={selectedDateRangeLabel}
                            wrapStyle={contentStyles.browseSection}
                        />
                    </View>
                )}
                onEndReached={() => {
                    if (!hasMore) {
                        return
                    }

                    void loadMore()
                }}
                onEndReachedThreshold={0.6}
                renderItem={renderItem}
                showsVerticalScrollIndicator={false}
                style={[
                    profileHistoryScreenStyles.list,
                    maxContentWidth ? { alignSelf: "center", maxWidth: maxContentWidth, width: "100%" } : null,
                ]}
            />
        </CatalogTemplate>
    )
}
