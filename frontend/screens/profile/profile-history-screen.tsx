import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
    ActivityIndicator,
    FlatList,
    Image,
    Modal,
    Platform,
    Pressable,
    Text,
    View,
    useWindowDimensions,
} from "react-native"
import type { StyleProp, TextStyle, ViewStyle } from "react-native"
import { router } from "expo-router"
import { Picker } from "@react-native-picker/picker"
import LottieView from "lottie-react-native"
import { CalendarList, LocaleConfig } from "react-native-calendars"

import { ContentTabBar, type ContentTabBarItem } from "@/components/content/content-tab-bar"
import { EmptyState } from "@/components/content/empty-state"
import { getModeBadgeStyle } from "@/components/content/recent-order-drafts-rail.utils"
import { contentStyles } from "@/components/content/content.styles"
import { CatalogTemplate } from "@/components/templates/catalog-template"
import { ROUTES } from "@/constants/routes"
import { STICKERS } from "@/constants/stickers"
import { usePaginatedData } from "@/hooks/shared/use-paginated-data"
import { useLanguage } from "@/providers/language-provider"
import { formatMoney } from "@/screens/checkout/checkout-screen.utils"
import { getOrders } from "@/services/api/orders"
import type { OrderHistoryBucket, OrderRead, OrderStatusCode } from "@/services/api/orders.types"
import { colors } from "@/theme/colors"
import { profileHistoryScreenStyles } from "./profile-history-screen.styles"
import {
    ORDER_STATUS_LABEL_KEYS,
    ORDER_STATUS_MESSAGE_KEYS,
    type ProfileHistoryFilters,
    buildDateRangeSelection,
    buildMarkedDateRange,
    buildOrderHistoryQuery,
    formatDateRangeTriggerValue,
    formatHistoryDate,
    getAppliedDateRange,
    getStatusCodesForBucket,
    getTodayCalendarDate,
} from "./profile-history-screen.utils"

const HISTORY_CALENDAR_LOCALE = "history-ru"
const PAGE_SIZE = 10
const EMPTY_FILTERS: ProfileHistoryFilters = {
    statusCode: null,
    createdFrom: null,
    createdTo: null,
}
const DATE_RANGE_MARKING_PALETTE = {
    rangeColor: "#dbeafe",
    rangeTextColor: colors.text,
    selectedColor: colors.primary,
    selectedTextColor: "#ffffff",
} as const

if (!LocaleConfig.locales[HISTORY_CALENDAR_LOCALE]) {
    LocaleConfig.locales[HISTORY_CALENDAR_LOCALE] = {
        dayNames: ["Воскресенье", "Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"],
        dayNamesShort: ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"],
        monthNames: [
            "Январь",
            "Февраль",
            "Март",
            "Апрель",
            "Май",
            "Июнь",
            "Июль",
            "Август",
            "Сентябрь",
            "Октябрь",
            "Ноябрь",
            "Декабрь",
        ],
        monthNamesShort: ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"],
        today: "Сегодня",
    }
}

LocaleConfig.defaultLocale = HISTORY_CALENDAR_LOCALE

type PickerOption<TValue extends string> = {
    key: string
    label: string
    value: TValue
}

type PickerSheetFieldProps<TValue extends string> = {
    disabled?: boolean
    label: string
    onChange: (value: TValue) => void
    options: readonly PickerOption<TValue>[]
    selectedValue: TValue
    title: string
    valueLabel: string
    wrapStyle?: StyleProp<ViewStyle>
    labelStyle?: StyleProp<TextStyle>
    triggerStyle?: StyleProp<ViewStyle>
}

type DateRangeSheetFieldProps = {
    label: string
    onChange: (range: Pick<ProfileHistoryFilters, "createdFrom" | "createdTo">) => void
    selectedRange: Pick<ProfileHistoryFilters, "createdFrom" | "createdTo">
    valueLabel: string
    wrapStyle?: StyleProp<ViewStyle>
    labelStyle?: StyleProp<TextStyle>
    triggerStyle?: StyleProp<ViewStyle>
}

function PickerSheetField<TValue extends string>({
    disabled = false,
    label,
    onChange,
    options,
    selectedValue,
    title,
    valueLabel,
    wrapStyle,
    labelStyle,
    triggerStyle,
}: PickerSheetFieldProps<TValue>) {
    const { t } = useLanguage()
    const [isOpen, setIsOpen] = useState(false)
    const [draftValue, setDraftValue] = useState(selectedValue)

    useEffect(() => {
        if (!isOpen) {
            setDraftValue(selectedValue)
        }
    }, [isOpen, selectedValue])

    return (
        <>
            <View style={wrapStyle}>
                <Text style={labelStyle}>{label}</Text>

                <Pressable
                    accessibilityLabel={label}
                    accessibilityRole="button"
                    disabled={disabled}
                    onPress={() => setIsOpen(true)}
                    style={({ pressed }) => [
                        contentStyles.browseTrigger,
                        !disabled && contentStyles.browseTriggerActive,
                        triggerStyle,
                        pressed && !disabled && contentStyles.browseTriggerPressed,
                    ]}
                >
                    <Text
                        numberOfLines={1}
                        style={[
                            contentStyles.browseTriggerValue,
                            disabled && contentStyles.browseTriggerPlaceholderValue,
                        ]}
                    >
                        {valueLabel}
                    </Text>
                </Pressable>
            </View>

            <Modal
                animationType="fade"
                onRequestClose={() => setIsOpen(false)}
                transparent
                visible={isOpen}
            >
                <View style={contentStyles.browsePickerBackdrop}>
                    <Pressable
                        accessibilityRole="button"
                        onPress={() => setIsOpen(false)}
                        style={contentStyles.browsePickerDismissArea}
                    />

                    <View style={contentStyles.browsePickerSheet}>
                        <View style={contentStyles.browsePickerHeader}>
                            <Text style={contentStyles.browsePickerTitle}>{title}</Text>

                            <View style={contentStyles.browsePickerActions}>
                                <Pressable
                                    accessibilityLabel={t("common.cancel")}
                                    accessibilityRole="button"
                                    onPress={() => setIsOpen(false)}
                                    style={({ pressed }) => [
                                        contentStyles.browsePickerAction,
                                        pressed && contentStyles.browsePickerActionPressed,
                                    ]}
                                >
                                    <Text style={contentStyles.browsePickerActionText}>
                                        {t("common.cancel")}
                                    </Text>
                                </Pressable>

                                <Pressable
                                    accessibilityLabel={t("common.done")}
                                    accessibilityRole="button"
                                    onPress={() => {
                                        onChange(draftValue)
                                        setIsOpen(false)
                                    }}
                                    style={({ pressed }) => [
                                        contentStyles.browsePickerPrimaryAction,
                                        pressed && contentStyles.browsePickerActionPressed,
                                    ]}
                                >
                                    <Text style={contentStyles.browsePickerPrimaryActionText}>
                                        {t("common.done")}
                                    </Text>
                                </Pressable>
                            </View>
                        </View>

                        <Picker
                            selectedValue={draftValue}
                            onValueChange={(value) => {
                                setDraftValue(value as TValue)
                            }}
                            style={contentStyles.browsePicker}
                        >
                            {options.map((option) => (
                                <Picker.Item key={option.key} label={option.label} value={option.value} />
                            ))}
                        </Picker>
                    </View>
                </View>
            </Modal>
        </>
    )
}

export function DateRangeSheetField({
    label,
    onChange,
    selectedRange,
    valueLabel,
    wrapStyle,
    labelStyle,
    triggerStyle,
}: DateRangeSheetFieldProps) {
    const { t } = useLanguage()
    const { width } = useWindowDimensions()
    const [isOpen, setIsOpen] = useState(false)
    const [draftRange, setDraftRange] = useState(selectedRange)
    const [visibleMonth, setVisibleMonth] = useState(selectedRange.createdTo ?? selectedRange.createdFrom ?? getTodayCalendarDate())
    const markedDates = useMemo(
        () => buildMarkedDateRange(draftRange.createdFrom, draftRange.createdTo, DATE_RANGE_MARKING_PALETTE),
        [draftRange.createdFrom, draftRange.createdTo],
    )
    const previewValue = useMemo(
        () => formatDateRangeTriggerValue(draftRange.createdFrom, draftRange.createdTo, t("profile.history.dateRangeEmpty")),
        [draftRange.createdFrom, draftRange.createdTo, t],
    )

    useEffect(() => {
        if (!isOpen) {
            setDraftRange(selectedRange)
            setVisibleMonth(selectedRange.createdTo ?? selectedRange.createdFrom ?? getTodayCalendarDate())
        }
    }, [isOpen, selectedRange])

    const handleApply = () => {
        onChange(getAppliedDateRange(draftRange))
        setIsOpen(false)
    }

    const handleReset = () => {
        onChange(EMPTY_FILTERS)
        setDraftRange(EMPTY_FILTERS)
        setIsOpen(false)
    }

    return (
        <>
            <View style={wrapStyle}>
                <Text style={labelStyle}>{label}</Text>

                <Pressable
                    accessibilityLabel={label}
                    accessibilityRole="button"
                    onPress={() => setIsOpen(true)}
                    style={({ pressed }) => [
                        contentStyles.browseTrigger,
                        contentStyles.browseTriggerActive,
                        triggerStyle,
                        pressed && contentStyles.browseTriggerPressed,
                    ]}
                >
                    <Text
                        numberOfLines={1}
                        style={contentStyles.browseTriggerValue}
                    >
                        {valueLabel}
                    </Text>
                </Pressable>
            </View>

            <Modal
                animationType="fade"
                onRequestClose={() => setIsOpen(false)}
                transparent
                visible={isOpen}
            >
                <View style={contentStyles.browsePickerBackdrop}>
                    <Pressable
                        accessibilityRole="button"
                        onPress={() => setIsOpen(false)}
                        style={contentStyles.browsePickerDismissArea}
                    />

                    <View style={profileHistoryScreenStyles.dateSheet}>
                        <View
                            style={[
                                contentStyles.browsePickerHeader,
                                profileHistoryScreenStyles.dateSheetHeader,
                            ]}
                        >
                            <Text
                                numberOfLines={1}
                                style={contentStyles.browsePickerTitle}
                            >
                                {previewValue}
                            </Text>

                            <View style={contentStyles.browsePickerActions}>
                                <Pressable
                                    accessibilityLabel={t("common.cancel")}
                                    accessibilityRole="button"
                                    onPress={() => setIsOpen(false)}
                                    style={({ pressed }) => [
                                        contentStyles.browsePickerAction,
                                        pressed && contentStyles.browsePickerActionPressed,
                                    ]}
                                >
                                    <Text style={contentStyles.browsePickerActionText}>
                                        {t("common.cancel")}
                                    </Text>
                                </Pressable>
                            </View>
                        </View>

                        <View style={profileHistoryScreenStyles.dateSheetBody}>
                            <View style={profileHistoryScreenStyles.calendarWrap}>
                                <CalendarList
                                    calendarWidth={Math.max(Math.round(width), 320)}
                                    current={visibleMonth}
                                    futureScrollRange={12}
                                    hideExtraDays
                                    horizontal
                                    keyboardShouldPersistTaps="handled"
                                    markingType="period"
                                    markedDates={markedDates}
                                    maxDate={getTodayCalendarDate()}
                                    onDayPress={(day) => {
                                        setDraftRange((currentValue) => buildDateRangeSelection(currentValue, day.dateString))
                                    }}
                                    onMonthChange={(month) => {
                                        setVisibleMonth(month.dateString)
                                    }}
                                    pagingEnabled
                                    pastScrollRange={12}
                                    renderArrow={(direction) => (
                                        <Text
                                            style={{
                                                color: colors.text,
                                                fontSize: 24,
                                                fontWeight: "700",
                                                lineHeight: 24,
                                            }}
                                        >
                                            {direction === "left" ? "‹" : "›"}
                                        </Text>
                                    )}
                                    showScrollIndicator={false}
                                    staticHeader
                                    style={profileHistoryScreenStyles.calendar}
                                    theme={{
                                        calendarBackground: colors.background,
                                        dayTextColor: colors.text,
                                        monthTextColor: colors.text,
                                        textDayFontSize: 16,
                                        textDayFontWeight: "600",
                                        textDisabledColor: "#c8d0d9",
                                        textMonthFontSize: 17,
                                        textMonthFontWeight: "800",
                                        textSectionTitleColor: colors.mutedText,
                                        todayTextColor: colors.primary,
                                        stylesheet: {
                                            day: {
                                                period: {
                                                    base: {
                                                        alignItems: "center",
                                                        height: 34,
                                                        justifyContent: "center",
                                                        overflow: "hidden",
                                                        width: 34,
                                                    },
                                                    text: {
                                                        color: colors.text,
                                                        fontSize: 16,
                                                        fontWeight: "600",
                                                    },
                                                },
                                            },
                                        },
                                    }}
                                />
                            </View>

                            <View style={profileHistoryScreenStyles.filterActions}>
                                <Pressable
                                    accessibilityLabel={t("common.reset")}
                                    accessibilityRole="button"
                                    onPress={handleReset}
                                    style={({ pressed }) => [
                                        profileHistoryScreenStyles.filterSecondaryButton,
                                        pressed && profileHistoryScreenStyles.filterSecondaryButtonPressed,
                                    ]}
                                >
                                    <Text style={profileHistoryScreenStyles.filterSecondaryButtonText}>
                                        {t("common.reset")}
                                    </Text>
                                </Pressable>

                                <Pressable
                                    accessibilityLabel={t("common.apply")}
                                    accessibilityRole="button"
                                    onPress={handleApply}
                                    style={({ pressed }) => [
                                        profileHistoryScreenStyles.filterPrimaryButton,
                                        pressed && profileHistoryScreenStyles.filterPrimaryButtonPressed,
                                    ]}
                                >
                                    <Text style={profileHistoryScreenStyles.filterPrimaryButtonText}>
                                        {t("common.apply")}
                                    </Text>
                                </Pressable>
                            </View>
                        </View>
                    </View>
                </View>
            </Modal>
        </>
    )
}

function OrderHistoryCard({ order }: { order: OrderRead }) {
    const { t } = useLanguage()
    const subtitle = order.delivery_string || order.delivery_address?.full_address || null
    const totalLabel = formatMoney(Number(order.grand_total), order.currency) ?? order.grand_total
    const isCompleted = order.history_bucket === "completed"
    const visibleItems = order.items.slice(0, 4)
    const statusLabel = t(ORDER_STATUS_LABEL_KEYS[order.status_code] ?? "profile.history.status.created")
    const statusMessage = t(ORDER_STATUS_MESSAGE_KEYS[order.status_code] ?? "profile.history.statusMessage.created")

    const handleOpenOrder = useCallback(() => {
        router.push({ pathname: ROUTES.payment, params: { orderId: String(order.id) } })
    }, [order.id])

    return (
        <View style={profileHistoryScreenStyles.historyCard}>
            <Pressable
                accessibilityLabel={`#${order.order_number}`}
                accessibilityRole="button"
                onPress={handleOpenOrder}
                style={({ pressed }) => pressed && profileHistoryScreenStyles.historyCardPressed}
            >
                <View style={profileHistoryScreenStyles.historyCardCollage}>
                    {visibleItems.map((item, index) => (
                        <View
                            key={`${order.id}-${item.id}-${item.variant_id}`}
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

                <View style={profileHistoryScreenStyles.historyCardBody}>
                    <View style={profileHistoryScreenStyles.historyCardHeader}>
                        <View style={profileHistoryScreenStyles.historyCardCopy}>
                            <Text style={profileHistoryScreenStyles.historyCardEyebrow}>{t("route.payment")}</Text>
                            <Text style={profileHistoryScreenStyles.historyCardTitle}>#{order.order_number}</Text>
                            {subtitle ? (
                                <Text numberOfLines={2} style={profileHistoryScreenStyles.historyCardSubtitle}>
                                    {subtitle}
                                </Text>
                            ) : null}
                        </View>

                        <View
                            style={[
                                profileHistoryScreenStyles.historyCardBadge,
                                isCompleted
                                    ? profileHistoryScreenStyles.historyCardBadgeCompleted
                                    : profileHistoryScreenStyles.historyCardBadgeActive,
                            ]}
                        >
                            <Text
                                numberOfLines={2}
                                style={[
                                    profileHistoryScreenStyles.historyCardBadgeText,
                                    isCompleted
                                        ? profileHistoryScreenStyles.historyCardBadgeTextCompleted
                                        : profileHistoryScreenStyles.historyCardBadgeTextActive,
                                ]}
                            >
                                {statusLabel}
                            </Text>
                        </View>
                    </View>

                    <Text style={profileHistoryScreenStyles.historyCardStatusMessage}>
                        {statusMessage}
                    </Text>

                    <View style={profileHistoryScreenStyles.historyCardMetaGrid}>
                        <View style={profileHistoryScreenStyles.historyCardMetaRow}>
                            <Text style={profileHistoryScreenStyles.historyCardMetaLabel}>{t("profile.history.createdAt")}</Text>
                            <Text style={profileHistoryScreenStyles.historyCardMetaValue}>
                                {formatHistoryDate(order.created_at)}
                            </Text>
                        </View>

                        <View style={profileHistoryScreenStyles.historyCardMetaRow}>
                            <Text style={profileHistoryScreenStyles.historyCardMetaLabel}>{t("profile.history.positions")}</Text>
                            <Text style={profileHistoryScreenStyles.historyCardMetaValue}>{order.items_count}</Text>
                        </View>
                    </View>
                </View>
            </Pressable>

            <View style={profileHistoryScreenStyles.historyCardDivider} />

            <View style={profileHistoryScreenStyles.historyCardFooter}>
                <Text style={profileHistoryScreenStyles.historyCardFooterLabel}>{t("checkout.grandTotalLabel")}</Text>
                <Text numberOfLines={1} style={profileHistoryScreenStyles.historyCardFooterValue}>{totalLabel}</Text>
            </View>
        </View>
    )
}

export default function ProfileHistoryScreen() {
    const { t } = useLanguage()
    const { width: windowWidth } = useWindowDimensions()
    const emptyHistorySticker = STICKERS.orderHistoryEmpty || STICKERS.favoritesEmpty
    const listRef = useRef<FlatList<OrderRead> | null>(null)
    const [bucket, setBucket] = useState<OrderHistoryBucket>("active")
    const [filters, setFilters] = useState<ProfileHistoryFilters>(EMPTY_FILTERS)
    const isWeb = Platform.OS === "web"
    const isDesktop = isWeb && windowWidth >= 1100
    const isTablet = isWeb && windowWidth >= 760
    const maxContentWidth = isDesktop ? 1180 : isTablet ? 960 : undefined

    const statusOptions = useMemo<readonly PickerOption<"all" | OrderStatusCode>[]>(
        () => [
            {
                key: "status-all",
                label: t("common.all"),
                value: "all",
            },
            ...getStatusCodesForBucket(bucket).map((statusCode) => ({
                key: statusCode,
                label: t(ORDER_STATUS_LABEL_KEYS[statusCode]),
                value: statusCode,
            })),
        ],
        [bucket, t],
    )
    const tabs = useMemo<ContentTabBarItem[]>(
        () => [
            {
                key: "active",
                label: t("profile.history.activeTab"),
                isActive: bucket === "active",
                onPress: () => setBucket("active"),
            },
            {
                key: "completed",
                label: t("profile.history.completedTab"),
                isActive: bucket === "completed",
                onPress: () => setBucket("completed"),
            },
        ],
        [bucket, t],
    )
    const historyChromeTemplate = useMemo(
        () => ({
            slots: {
                headerCenter: (
                    <View style={profileHistoryScreenStyles.headerTabsSlot}>
                        <ContentTabBar tabs={tabs} variant="default" />
                    </View>
                ),
            },
        }),
        [tabs],
    )
    const selectedStatusValue = filters.statusCode ?? "all"
    const selectedStatusLabel = statusOptions.find((option) => option.value === selectedStatusValue)?.label ?? t("common.all")
    const selectedDateRangeLabel = formatDateRangeTriggerValue(
        filters.createdFrom,
        filters.createdTo,
        t("profile.history.dateRangeEmpty"),
    )
    const hasActiveFilters = Boolean(filters.statusCode || filters.createdFrom || filters.createdTo)

    const { error, hasMore, items, loadMore, loading, loadingMore, reload } = usePaginatedData<OrderRead>({
        deps: [bucket, filters.statusCode, filters.createdFrom, filters.createdTo],
        fetchPage: async ({ limit, offset }) => getOrders(buildOrderHistoryQuery(bucket, filters, limit, offset)),
        getKey: (item) => String(item.id),
        pageSize: PAGE_SIZE,
    })

    useEffect(() => {
        const allowedStatusCodes = [...getStatusCodesForBucket(bucket)]

        setFilters((current) => {
            if (!current.statusCode || allowedStatusCodes.includes(current.statusCode)) {
                return current
            }

            return {
                ...current,
                statusCode: null,
            }
        })
    }, [bucket])

    useEffect(() => {
        listRef.current?.scrollToOffset({ offset: 0, animated: false })
    }, [bucket, filters.createdFrom, filters.createdTo, filters.statusCode])

    const emptyStateDescription = useMemo(() => {
        if (hasActiveFilters) {
            return t("profile.history.searchEmptyDescription")
        }

        if (bucket === "active") {
            return t("profile.history.activeEmptyMotivation")
        }

        return t("profile.history.completedEmptyMotivation")
    }, [bucket, hasActiveFilters, t])

    const renderItem = useCallback(
        ({ item }: { item: OrderRead }) => (
            <View style={profileHistoryScreenStyles.cardWrap}>
                <OrderHistoryCard order={item} />
            </View>
        ),
        [],
    )

    return (
        <CatalogTemplate chromeTemplate={historyChromeTemplate} style={profileHistoryScreenStyles.screen}>
            <FlatList
                ref={listRef}
                contentContainerStyle={[
                    profileHistoryScreenStyles.listContent,
                    items.length === 0 ? profileHistoryScreenStyles.listContentEmpty : null,
                ]}
                data={items}
                keyExtractor={(item) => String(item.id)}
                keyboardShouldPersistTaps="handled"
                ListEmptyComponent={
                    loading ? (
                        <View style={profileHistoryScreenStyles.loaderWrap}>
                            <ActivityIndicator color={colors.primary} />
                        </View>
                    ) : error ? (
                        <EmptyState
                            eyebrow={t("profile.history.title")}
                            title={t("profile.history.loadFailedTitle")}
                            description={error}
                            actionLabel={t("common.retry")}
                            onPressAction={() => {
                                void reload()
                            }}
                        />
                    ) : (
                        <View
                            style={profileHistoryScreenStyles.searchEmptyState}
                        >
                            {emptyHistorySticker.kind === "lottie" ? (
                                <LottieView
                                    autoPlay
                                    loop
                                    source={emptyHistorySticker.source}
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
                                    {t("profile.history.searchOpenCatalog")}
                                </Text>
                            </Pressable>
                        </View>
                    )
                }
                ListFooterComponent={
                    !loadingMore ? null : (
                        <View style={profileHistoryScreenStyles.footerLoaderWrap}>
                            <ActivityIndicator color={colors.primary} />
                        </View>
                    )
                }
                ListHeaderComponent={(
                    <View style={profileHistoryScreenStyles.controlsWrap}>
                        <View style={contentStyles.browseControlsRow}>
                            <DateRangeSheetField
                                label={t("profile.history.dateRangeField")}
                                labelStyle={contentStyles.browseSectionLabel}
                                onChange={(range) => {
                                    setFilters((current) => ({
                                        ...current,
                                        createdFrom: range.createdFrom,
                                        createdTo: range.createdTo,
                                    }))
                                }}
                                selectedRange={filters}
                                valueLabel={selectedDateRangeLabel}
                                wrapStyle={contentStyles.browseSectionCompact}
                            />

                            <PickerSheetField
                                label={t("profile.history.statusField")}
                                labelStyle={[
                                    contentStyles.browseSectionLabel,
                                    contentStyles.browseSectionLabelEnd,
                                ]}
                                onChange={(value) => {
                                    setFilters((current) => ({
                                        ...current,
                                        statusCode: value === "all" ? null : value,
                                    }))
                                }}
                                options={statusOptions}
                                selectedValue={selectedStatusValue}
                                title={t("profile.history.statusField")}
                                triggerStyle={contentStyles.browseTriggerEnd}
                                valueLabel={selectedStatusLabel}
                                wrapStyle={[
                                    contentStyles.browseSectionCompact,
                                    contentStyles.browseSectionCompactEnd,
                                ]}
                            />
                        </View>
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
