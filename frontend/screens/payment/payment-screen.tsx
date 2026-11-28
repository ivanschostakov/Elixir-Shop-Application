import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
    ActivityIndicator,
    AppState,
    Alert,
    Animated,
    Easing,
    Image,
    LayoutChangeEvent,
    Linking,
    Pressable,
    ScrollView,
    Text,
    View,
} from "react-native"
import * as Clipboard from "expo-clipboard"
import { router, useLocalSearchParams } from "expo-router"
import LottieView from "lottie-react-native"

import { createStickyFooterStyles } from "@/components/footer/sticky-footer.styles"
import { useApplyScreenTemplate } from "@/components/templates/screen-template.hooks"
import { ROUTES } from "@/constants/routes"
import { STICKERS } from "@/constants/stickers"
import { clearBasketSnapshot } from "@/hooks/basket/basket-store"
import { useBasket } from "@/hooks/basket/use-basket"
import { setOrderDraftSnapshot } from "@/hooks/order-draft/order-draft-store"
import { useOrderDraft } from "@/hooks/order-draft/use-order-draft"
import { useAuth } from "@/providers/auth-provider"
import { useLanguage } from "@/providers/language-provider"
import {
    buildCheckoutDraftFromBasket,
    formatMoney,
    formatRecipientName,
    getDraftRecipient,
    getSelfRecipient,
    parseDraftId,
} from "@/screens/checkout/checkout-screen.utils"
import { createPaymentScreenStyles } from "@/screens/payment/payment-screen.styles"
import { confirmedPaidOrderId, mergePaymentState, resolvePaymentPhase, visibleOrderTotal } from "@/screens/payment/payment-state"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { createGuestOrder, isGuestPhoneExistsError } from "@/services/api/guest"
import { ApiError } from "@/services/api/client"
import type { GuestOrderPayload } from "@/services/api/guest.types"
import { createOrder, getOrder, repeatOrder } from "@/services/api/orders"
import type { OrderItemRead, OrderRead } from "@/services/api/orders.types"
import { readSubmittedOrder, submitCheckout } from "@/services/api/payments"
import { getGuestCheckoutEmail, setGuestCheckoutEmail } from "@/screens/checkout/guest-checkout-email"
import type { PaymentStatusRead } from "@/services/api/payments.types"
import { clearGuestCart } from "@/services/guest-cart"
import { syncOrderStatusNotifications } from "@/services/notifications/order-status-notifications"
import { queueStartupNotice } from "@/services/notifications/startup-notices"
import { getAuthTokens } from "@/services/auth/session"
import type { OrderDraftItemRead, OrderDraftRead } from "@/services/api/order-drafts.types"
import { ORDER_STATUS_LABEL_KEYS } from "@/screens/profile/profile-history-screen.utils"
import { getErrorMessage, showBackendErrorAlert } from "@/utils/errors"
import { confirmedBalanceAmount, formatAppliedDiscount, orderDiscountRows } from "@/utils/discount-display"
import { parsePositiveRouteId } from "@/utils/route-params"

type PaymentMethod = "later" | "sbp"
type RewardMode = "cashback" | "promo"
type PaymentPhase = "select" | "processing" | "waiting" | "sbp" | "pending" | "success" | "failure"
type SummarySection = "contact" | "items"

const PAYMENT_CHROME_TEMPLATE = { footer: "none" } as const
const CONFETTI_COLORS = ["#E94E77", "#F6C85F", "#3CAEA3", "#20639B", "#F17300", "#7B61FF"] as const
const CONFETTI_PIECES = Array.from({ length: 64 }, (_, index) => ({
    color: CONFETTI_COLORS[index % CONFETTI_COLORS.length],
    delay: (index % 8) * 18,
    drift: ((index % 9) - 4) * 16,
    left: 5 + ((index * 31) % 90),
    rotation: index % 2 === 0 ? "210deg" : "-180deg",
    size: 7 + (index % 6),
    top: -24 - (index % 7) * 12,
    travel: 320 + (index % 8) * 34,
}))

function getPaymentStateError(payment: PaymentStatusRead | null, fallback: string) {
    if (!payment?.payment_status) {
        return fallback
    }

    switch (payment.payment_status) {
        case "canceled":
            return "Платеж был отменен."
        case "refunded":
            return "Платеж был возвращен."
        case "error":
            return "Не удалось завершить оплату."
        case "hold":
            return "Платеж ожидает подтверждения. Мы обновим статус сразу после ответа IntellectMoney."
        case "partial":
            return "Платеж прошел частично. Пожалуйста, свяжитесь с менеджером."
        default:
            return fallback
    }
}

function isTemporaryStatusError(error: unknown) {
    if (error instanceof ApiError) {
        const code = (error.body as { detail?: { code?: string } } | null)?.detail?.code
        return code === "settlement_pending" || error.status === 408 || error.status === 429 || error.status >= 500
    }
    return error instanceof TypeError
}

function parsePaymentMethod(value: string | string[] | undefined): PaymentMethod | null {
    const rawValue = Array.isArray(value) ? value[0] : value
    if (rawValue === "later" || rawValue === "sbp") {
        return rawValue
    }
    return null
}

function resolvePaymentMethod(value: string | null | undefined): PaymentMethod | null {
    return value === "later" || value === "sbp" ? value : null
}

function parseRouteString(value: string | string[] | undefined) {
    const rawValue = Array.isArray(value) ? value[0] : value
    const trimmedValue = rawValue?.trim()
    return trimmedValue || null
}

function buildGuestOrderPayload(orderDraft: OrderDraftRead, paymentMethod: PaymentMethod, buyerEmail: string): GuestOrderPayload {
    const deliveryAddress = orderDraft.delivery_address
    const recipient = getDraftRecipient(orderDraft)

    if (!deliveryAddress || !recipient) {
        throw new Error("Guest order requires delivery and recipient data")
    }

    return {
        automatic_checkout: true,
        buyer_email: buyerEmail.trim().toLowerCase(),
        items: orderDraft.items.map((item) => ({
            variant_id: item.variant_id,
            quantity: item.quantity,
        })),
        delivery_address: {
            mode: deliveryAddress.mode,
            provider: deliveryAddress.provider,
            country_code: deliveryAddress.country_code,
            name: deliveryAddress.name,
            full_address: deliveryAddress.full_address,
            details: deliveryAddress.details,
            city: deliveryAddress.city,
            postal_code: deliveryAddress.postal_code,
            latitude: deliveryAddress.latitude,
            longitude: deliveryAddress.longitude,
            provider_reference: deliveryAddress.provider_reference,
            ...(deliveryAddress.provider === "YANDEX"
                ? {
                      delivery_calculation: {
                          delivery_sum: Number(orderDraft.delivery_total),
                          period_min: orderDraft.delivery_period_min ?? 0,
                          period_max: orderDraft.delivery_period_max ?? 0,
                          currency: orderDraft.currency,
                      },
                  }
                : {}),
        },
        recipient: {
            name: recipient.name,
            surname: recipient.surname,
            phone: recipient.phone,
            email: recipient.email,
        },
        payment_method: paymentMethod,
    }
}

export default function PaymentScreen() {
    const stickyFooterStyles = useThemeStyles(createStickyFooterStyles)
    const paymentScreenStyles = useThemeStyles(createPaymentScreenStyles)
    const { acceptSession, isAuthenticated, user, milestones } = useAuth()
    const { t } = useLanguage()
    const params = useLocalSearchParams<{
        code?: string | string[]
        draftId?: string | string[]
        paymentMethod?: string | string[]
        orderId?: string | string[]
        rewardMode?: string | string[]
    }>()
    const draftId = parseDraftId(params.draftId)
    const routePaymentMethod = parsePaymentMethod(params.paymentMethod)
    const routeOrderId = parsePositiveRouteId(params.orderId)
    const routePromoCode = parseRouteString(params.code)
    const rewardMode: RewardMode = parseRouteString(params.rewardMode) === "promo" ? "promo" : "cashback"
    const isBasketCheckout = draftId === null
    const { basket, loading: basketLoading } = useBasket()
    const { orderDraft: savedOrderDraft, error: savedDraftError, loading: savedDraftLoading, reload: reloadDraft } = useOrderDraft(draftId)
    const orderDraft = useMemo(
        () => (isBasketCheckout && basket ? buildCheckoutDraftFromBasket(basket) : savedOrderDraft),
        [basket, isBasketCheckout, savedOrderDraft],
    )
    const error = isBasketCheckout ? null : savedDraftError
    const [selectedMethod, setSelectedMethod] = useState<PaymentMethod>(routePaymentMethod ?? "sbp")
    const [order, setOrder] = useState<OrderRead | null>(null)
    const loading = !order && !routeOrderId && (isBasketCheckout ? basketLoading : savedDraftLoading)
    const [payment, setPayment] = useState<PaymentStatusRead | null>(null)
    const [submitting, setSubmitting] = useState(false)
    const [isRepeating, setIsRepeating] = useState(false)
    const [phase, setPhase] = useState<PaymentPhase>("select")
    const paidOrderId = confirmedPaidOrderId(user?.id, order, payment)
    const checkMilestones = milestones?.check
    useEffect(() => {
        if (paidOrderId) void checkMilestones?.("paid")
    }, [paidOrderId, checkMilestones])
    const [errorMessage, setErrorMessage] = useState<string | null>(null)
    const hasAutoStartedRef = useRef(false)
    const [loadingOrder, setLoadingOrder] = useState(false)
    const [orderLoadError, setOrderLoadError] = useState<string | null>(null)
    const [isQrVisualReady, setIsQrVisualReady] = useState(false)
    const [isQrImageFailed, setIsQrImageFailed] = useState(false)
    const [isSuccessVisualReady, setIsSuccessVisualReady] = useState(false)
    const [isContactExpanded, setIsContactExpanded] = useState(true)
    const [isItemsExpanded, setIsItemsExpanded] = useState(true)
    const scrollRef = useRef<ScrollView>(null)
    const confettiProgress = useRef(new Animated.Value(0)).current
    const paymentStatusRequestIdRef = useRef(0)
    const startingPaymentRef = useRef(false)
    const recoverLegacyCheckout = useRef(false)
    const sectionPositionsRef = useRef<Record<SummarySection, number>>({
        contact: 0,
        items: 0,
    })

    const openDiscover = useCallback(() => {
        router.replace(ROUTES.discover)
    }, [])

    const openCheckout = useCallback(() => {
        if (!order) {
            router.replace(
                draftId
                    ? { pathname: ROUTES.checkout, params: { draftId: String(draftId) } }
                    : ROUTES.checkout,
            )
            return
        }

        openDiscover()
    }, [draftId, openDiscover, order])

    useEffect(() => {
        if (routePaymentMethod) {
            setSelectedMethod(routePaymentMethod)
        }
    }, [routePaymentMethod])

    useEffect(() => {
        return () => {
            paymentStatusRequestIdRef.current += 1
        }
    }, [])

    useEffect(() => {
        if (!routeOrderId || order) {
            return
        }

        setLoadingOrder(true)
        setOrderLoadError(null)

        let isActive = true
        void (async () => {
            try {
                const nextOrder = await getOrder(routeOrderId)
                if (!isActive) {
                    return
                }
                setOrder(nextOrder)
                if (!routePaymentMethod && (nextOrder.payment_method === "later" || nextOrder.payment_method === "sbp")) {
                    setSelectedMethod(nextOrder.payment_method)
                }
            } catch (loadError) {
                if (!isActive) {
                    return
                }
                const message = getErrorMessage(loadError, t("payment.orderMissingMessage"))
                setOrderLoadError(message)
                showBackendErrorAlert(loadError, message)
            } finally {
                if (isActive) {
                    setLoadingOrder(false)
                }
            }
        })()

        return () => {
            isActive = false
        }
    }, [order, routeOrderId, routePaymentMethod, t])

    const resolvedRecipient = order?.recipient ?? getDraftRecipient(orderDraft) ?? getSelfRecipient(user)
    const resolvedItemsCount = order?.items.length ?? orderDraft?.items.length ?? 0
    const resolvedOrderNumber = payment?.order_number ?? order?.order_number ?? null
    const resolvedOrderCode = payment?.order_code ?? order?.order_code ?? resolvedOrderNumber
    const resolvedAddress = order?.delivery_address?.full_address ?? orderDraft?.delivery_address?.full_address ?? "—"
    const resolvedItems = useMemo<(OrderItemRead | OrderDraftItemRead)[]>(
        () => order?.items ?? orderDraft?.items ?? [],
        [order?.items, orderDraft?.items],
    )
    const resolvedPaymentMethod =
        resolvePaymentMethod(payment?.payment_method)
        ?? resolvePaymentMethod(order?.payment_method)
        ?? selectedMethod
    const totalLabel = useMemo(() => {
        const total = visibleOrderTotal(order, payment)
        const currency = order?.currency ?? orderDraft?.currency
        if (total == null || !currency) {
            return null
        }
        return formatMoney(Number(total), currency)
    }, [payment, order, orderDraft?.currency])
    const basketSubtotalLabel = useMemo(() => {
        const subtotal = order?.basket_subtotal ?? orderDraft?.basket_subtotal
        const currency = order?.currency ?? orderDraft?.currency
        if (!subtotal || !currency) {
            return null
        }
        return formatMoney(Number(subtotal), currency)
    }, [order?.basket_subtotal, order?.currency, orderDraft?.basket_subtotal, orderDraft?.currency])
    const deliveryTotalLabel = useMemo(() => {
        const deliveryTotal = order?.delivery_total ?? orderDraft?.delivery_total
        const currency = order?.currency ?? orderDraft?.currency
        if (!deliveryTotal || !currency) {
            return null
        }
        return formatMoney(Number(deliveryTotal), currency)
    }, [order?.currency, order?.delivery_total, orderDraft?.currency, orderDraft?.delivery_total])
    const qrSourceUri = payment?.qr_image ?? null
    const qrLinkTarget = payment?.qr_url?.trim() || null
    const qrImageSource = useMemo(() => {
        if (!qrSourceUri) {
            return null
        }

        const normalizedUri = qrSourceUri.trim()
        if (!normalizedUri) {
            return null
        }

        if (normalizedUri.startsWith("data:")) {
            return { uri: normalizedUri } as const
        }

        return { uri: normalizedUri, cache: "force-cache" as const }
    }, [qrSourceUri])
    const shouldRenderQrImage = Boolean(qrImageSource && !isQrImageFailed)
    const hasResolvedOrderInfo = Boolean(
        (order?.delivery_address ?? orderDraft?.delivery_address)
        && resolvedRecipient
        && resolvedItemsCount > 0,
    )
    const resolvedOrderStatusLabel = order?.status_code
        ? t(ORDER_STATUS_LABEL_KEYS[order.status_code] ?? "profile.history.status.created")
        : null
    const canContinue = hasResolvedOrderInfo && !submitting
    const canRetry = Boolean(order && payment?.can_retry && !order.is_canceled && !order.is_paid && !payment.checkout_progress)
    const missingStateMessage = orderLoadError ?? t("payment.orderMissingMessage")
    const shouldShowFooter = hasResolvedOrderInfo || loading || loadingOrder || phase !== "select" || submitting
    const isRepeatableOrder = order?.history_bucket === "completed"
    const recipientLabel = formatRecipientName(resolvedRecipient)
    const deliveryLabel = [
        order?.selected_delivery_service ?? orderDraft?.delivery_address?.provider,
        resolvedAddress,
    ].filter(Boolean).join(" • ") || "—"

    const handleCopyOrderCode = useCallback(async () => {
        if (!resolvedOrderCode) {
            return
        }

        const copiedCode = resolvedOrderCode.startsWith("#") ? resolvedOrderCode : `#${resolvedOrderCode}`
        await Clipboard.setStringAsync(copiedCode)
        Alert.alert(t("payment.orderCopiedTitle"), copiedCode)
    }, [resolvedOrderCode, t])

    const handleRepeatOrder = useCallback(async () => {
        if (!order?.id || isRepeating || !isRepeatableOrder) {
            return
        }

        setIsRepeating(true)

        try {
            const repeatedDraft = await repeatOrder(order.id)
            setOrderDraftSnapshot(repeatedDraft)
            router.push({ pathname: ROUTES.checkout, params: { draftId: String(repeatedDraft.id) } })
        } catch (repeatError) {
            showBackendErrorAlert(repeatError, t("payment.repeatFailedMessage"))
            Alert.alert(
                t("payment.repeatFailedTitle"),
                getErrorMessage(repeatError, t("payment.repeatFailedMessage")),
            )
        } finally {
            setIsRepeating(false)
        }
    }, [isRepeatableOrder, isRepeating, order?.id, t])

    const openQrLink = useCallback(() => {
        if (!qrLinkTarget) {
            return
        }

        void Linking.openURL(qrLinkTarget).catch(() => Alert.alert(t("payment.title"), t("payment.bankLinkFailed")))
    }, [qrLinkTarget, t])

    const handleSectionLayout = useCallback(
        (section: SummarySection) =>
        (event: LayoutChangeEvent) => {
            sectionPositionsRef.current[section] = event.nativeEvent.layout.y
        },
        [],
    )

    const scrollToSection = useCallback((section: SummarySection) => {
        requestAnimationFrame(() => {
            scrollRef.current?.scrollTo({
                y: Math.max(sectionPositionsRef.current[section] - 12, 0),
                animated: true,
            })
        })
    }, [])

    const handleToggleSection = useCallback((section: SummarySection) => {
        if (section === "contact") {
            const willExpand = !isContactExpanded
            setIsContactExpanded(willExpand)
            if (willExpand) {
                scrollToSection(section)
            }
            return
        }

        const willExpand = !isItemsExpanded
        setIsItemsExpanded(willExpand)
        if (willExpand) {
            scrollToSection(section)
        }
    }, [isContactExpanded, isItemsExpanded, scrollToSection])

    const handleStartPayment = useCallback(async (methodOverride?: PaymentMethod, explicitRetry = false) => {
        const effectiveMethod = methodOverride ?? selectedMethod
        if (startingPaymentRef.current || (!orderDraft && !order)) {
            return
        }

        startingPaymentRef.current = true
        const requestId = ++paymentStatusRequestIdRef.current
        const isActive = () => paymentStatusRequestIdRef.current === requestId
        setSubmitting(true)
        setPhase("processing")
        setErrorMessage(null)
        let nextOrder = order

        try {
            if (!nextOrder) {
                if (!orderDraft) {
                    throw new Error(t("payment.orderMissingMessage"))
                }

                if (isBasketCheckout && !isAuthenticated) {
                    const recoveryEmail = getGuestCheckoutEmail()
                    if (!/^[^@\s]+@[^@]+\.[^@]+$/.test(recoveryEmail)) throw new Error(t("auth.error.invalidEmail"))
                    const guestOrderResponse = await createGuestOrder(buildGuestOrderPayload(orderDraft, effectiveMethod, recoveryEmail))
                    setGuestCheckoutEmail("")
                    acceptSession(guestOrderResponse)
                    nextOrder = guestOrderResponse.order
                    clearBasketSnapshot()
                    void clearGuestCart({ updateSnapshot: false }).catch(() => undefined)
                } else {
                    nextOrder = await createOrder({
                        automatic_checkout: true,
                        ...(isBasketCheckout ? {} : { draft_id: orderDraft.id }),
                        ...(routePromoCode ? { code: routePromoCode } : {}),
                        reward_mode: routePromoCode ? "order_referral" : rewardMode,
                        payment_method: effectiveMethod,
                    })
                    if (isBasketCheckout) {
                        clearBasketSnapshot()
                    }
                }
                if (!isActive()) return
                setOrder(nextOrder)
                router.setParams({ orderId: String(nextOrder.id), paymentMethod: effectiveMethod })
                const orderSession = getAuthTokens()?.sessionId
                void queueStartupNotice(async () => {
                    if (orderSession != null && orderSession === getAuthTokens()?.sessionId) {
                        await syncOrderStatusNotifications()
                    }
                })
            }

            const nextPayment = order
                ? await submitCheckout({ order_id: nextOrder.id, payment_method: effectiveMethod }, isActive, !explicitRetry)
                : await readSubmittedOrder(nextOrder.id)
            if (!nextPayment || !isActive()) return
            setPayment((currentPayment) => mergePaymentState(currentPayment, nextPayment))
            if (typeof nextPayment.amount_rubles === "number" && Number.isFinite(nextPayment.amount_rubles)) {
                setOrder({ ...nextOrder, grand_total: String(nextPayment.amount_rubles) })
            }
            const nextPhase = resolvePaymentPhase(nextPayment, effectiveMethod, nextOrder)
            setPhase(nextPhase)
            if (nextPhase === "failure") {
                setErrorMessage(getPaymentStateError(nextPayment, t("payment.failureMessage")))
            }
        } catch (paymentError) {
            if (!isActive()) return
            if (paymentError instanceof ApiError && (paymentError.body as { detail?: { code?: string } })?.detail?.code === "draft_repriced") {
                await reloadDraft()
                if (!isActive()) return
                Alert.alert(t("payment.title"), paymentError.message)
                openCheckout()
                return
            }
            if (isTemporaryStatusError(paymentError)) {
                if (nextOrder) {
                    // The saved order owns its server job. Recover by reading it, never by resubmitting it.
                    setPhase("waiting")
                } else {
                    setErrorMessage(t("payment.checkHistoryOnDisconnect"))
                    setPhase("failure")
                }
                return
            }
            const fallback = nextOrder ? t("payment.paymentCreateFailed") : t("payment.orderCreateFailed")
            const message = getErrorMessage(paymentError, fallback)

            if (isGuestPhoneExistsError(paymentError)) {
                setErrorMessage(t("checkout.existingPhoneMessage"))
                Alert.alert(
                    t("checkout.existingPhoneTitle"),
                    t("checkout.existingPhoneMessage"),
                    [
                        {
                            text: t("payment.backToCheckout"),
                            style: "cancel",
                            onPress: () => {
                                router.replace(ROUTES.checkout)
                            },
                        },
                        {
                            text: t("auth.entry.login"),
                            onPress: () => {
                                router.replace(ROUTES.login)
                            },
                        },
                    ],
                )
                setPhase("failure")
                return
            }

            setErrorMessage(message)
            showBackendErrorAlert(paymentError, message)
            setPhase("failure")
        } finally {
            startingPaymentRef.current = false
            if (isActive()) {
                setSubmitting(false)
            }
        }
    }, [openCheckout, reloadDraft, acceptSession, isAuthenticated, isBasketCheckout, order, orderDraft, rewardMode, routePromoCode, selectedMethod, t])

    const handleRetryPayment = useCallback(() => {
        if (order) void handleStartPayment(resolvedPaymentMethod, true)
    }, [handleStartPayment, order, resolvedPaymentMethod])

    const footerCtaState = useMemo(() => {
        if (loading || loadingOrder) {
            return {
                busy: true,
                disabled: true,
                label: t("payment.loadingDraft"),
                onPress: null as (() => void) | null,
            }
        }

        if (submitting || phase === "processing") {
            const label = !order
                ? t("payment.processingOrder")
                : resolvedPaymentMethod === "later"
                    ? t("payment.processingLater")
                    : t("payment.processingSbp")

            return {
                busy: true,
                disabled: true,
                label,
                onPress: null as (() => void) | null,
            }
        }

        if (phase === "sbp") {
            if (qrLinkTarget) return {
                busy: false, disabled: false, label: t("payment.tapToPayPlaceholder"), onPress: openQrLink,
            }
            return {
                busy: true,
                disabled: true,
                label: !qrImageSource && !qrLinkTarget
                    ? t("payment.processingSbp")
                    : !isQrVisualReady ? t("payment.processingVisual") : t("payment.awaitingPayment"),
                onPress: null as (() => void) | null,
            }
        }

        if (phase === "pending" || phase === "waiting") {
            return {
                busy: false,
                disabled: false,
                label: t("route.profileHistory"),
                onPress: () => router.replace(ROUTES.profileHistory),
            }
        }

        if (isRepeatableOrder) {
            return {
                busy: isRepeating,
                disabled: isRepeating,
                label: isRepeating ? t("payment.repeatLoading") : t("payment.repeatOrder"),
                onPress: () => {
                    void handleRepeatOrder()
                },
            }
        }

        if (phase === "success") {
            if (!isSuccessVisualReady) {
                return {
                    busy: true,
                    disabled: true,
                    label: t("payment.processingVisual"),
                    onPress: null as (() => void) | null,
                }
            }

            return {
                busy: false,
                disabled: false,
                label: t("payment.goHome"),
                onPress: openDiscover,
            }
        }

        if (phase === "failure" && canRetry) {
            return {
                busy: false,
                disabled: false,
                label: t("payment.retry"),
                onPress: handleRetryPayment,
            }
        }

        if (phase === "failure") {
            return {
                busy: false,
                disabled: false,
                label: t("payment.goHome"),
                onPress: openDiscover,
            }
        }

        return {
            busy: true,
            disabled: true,
            label: t("payment.loading"),
            onPress: null as (() => void) | null,
        }
    }, [
        canRetry,
        handleRepeatOrder,
        handleRetryPayment,
        isRepeatableOrder,
        isRepeating,
        isQrVisualReady,
        loading,
        loadingOrder,
        openDiscover,
        order,
        phase,
        qrImageSource,
        qrLinkTarget,
        openQrLink,
        isSuccessVisualReady,
        resolvedPaymentMethod,
        submitting,
        t,
    ])

    const headerTitle = resolvedOrderNumber ? `#${resolvedOrderNumber}` : t("payment.title")
    const headerCenterSlot = useMemo(() => {
        if (!resolvedOrderNumber) {
            return null
        }

        return (
            <Pressable
                accessibilityLabel={t("payment.copyOrderNumber")}
                accessibilityRole="button"
                onPress={() => {
                    void handleCopyOrderCode()
                }}
                style={({ pressed }) => [
                    paymentScreenStyles.headerTitleButton,
                    pressed && paymentScreenStyles.headerTitleButtonPressed,
                ]}
            >
                <Text numberOfLines={1} style={paymentScreenStyles.headerTitleText}>{headerTitle}</Text>
            </Pressable>
        )
    }, [handleCopyOrderCode, headerTitle, paymentScreenStyles, resolvedOrderNumber, t])

    const paymentChromeTemplate = useMemo(() => {
        const headerSlots = headerCenterSlot ? { headerCenter: headerCenterSlot } : undefined

        if (!shouldShowFooter) {
            return {
                ...PAYMENT_CHROME_TEMPLATE,
                title: headerCenterSlot ? null : headerTitle,
                slots: headerSlots,
            }
        }

        return {
            footer: "nav+customAction" as const,
            title: headerCenterSlot ? null : headerTitle,
            slots: {
                ...headerSlots,
                footer: (
                    <View style={paymentScreenStyles.footerActionStack}>
                        <Pressable
                            accessibilityLabel={footerCtaState.label}
                            accessibilityRole="button"
                            disabled={footerCtaState.disabled}
                            onPress={footerCtaState.onPress ?? undefined}
                            style={({ pressed }) => [
                                stickyFooterStyles.actionButton,
                                footerCtaState.disabled && stickyFooterStyles.actionButtonDisabled,
                                pressed && !footerCtaState.disabled && stickyFooterStyles.actionButtonPressed,
                            ]}
                        >
                            <View style={paymentScreenStyles.footerCtaContent}>
                                {footerCtaState.busy ? <ActivityIndicator color="#FFFFFF" size="small" /> : null}
                                <Text style={stickyFooterStyles.actionButtonText}>{footerCtaState.label}</Text>
                            </View>
                        </Pressable>
                    </View>
                ),
            },
        }
    }, [
        footerCtaState.busy,
        footerCtaState.disabled,
        footerCtaState.label,
        footerCtaState.onPress,
        headerCenterSlot,
        headerTitle,
        paymentScreenStyles,
        shouldShowFooter,
        stickyFooterStyles,
    ])

    useApplyScreenTemplate("feed", paymentChromeTemplate)

    useEffect(() => {
        if (routeOrderId || order || hasAutoStartedRef.current || phase !== "select") return
        if (params.orderId != null || !routePaymentMethod) {
            hasAutoStartedRef.current = true
            router.replace(params.orderId != null ? ROUTES.profileHistory : ROUTES.checkout)
            return
        }
        if (loading || loadingOrder || !canContinue) return
        hasAutoStartedRef.current = true
        void handleStartPayment(routePaymentMethod)
    }, [canContinue, handleStartPayment, loading, loadingOrder, order, params.orderId, phase, routeOrderId, routePaymentMethod])

    useEffect(() => {
        if (!order?.id || payment || submitting || phase !== "select") {
            return
        }

        const method = resolvePaymentMethod(order.payment_method)
        if (order.is_canceled || !method) {
            setPhase("failure")
            setErrorMessage(t("payment.failureMessage"))
            return
        }
        const requestId = ++paymentStatusRequestIdRef.current
        const active = () => paymentStatusRequestIdRef.current === requestId
        setPhase("processing")
        void (async () => {
            try {
                const next = await submitCheckout({ order_id: order.id, payment_method: method }, active, true)
                if (!next || !active()) return
                setPayment(current => mergePaymentState(current, next))
                const nextPhase = resolvePaymentPhase(next, method, order)
                setPhase(nextPhase)
                if (nextPhase === "failure") setErrorMessage(getPaymentStateError(next, t("payment.failureMessage")))
            } catch (error) {
                if (!active()) return
                if (isTemporaryStatusError(error)) {
                    recoverLegacyCheckout.current = true
                    setPhase("waiting")
                    return
                }
                setErrorMessage(getErrorMessage(error, t("payment.statusCheckFailed")))
                setPhase("failure")
            }
        })()
    }, [order, payment, phase, submitting, t])

    useEffect(() => {
        const orderId = payment?.order_id ?? order?.id
        if (!orderId || (phase !== "waiting" && phase !== "sbp")) return
        let active = true
        let delay = 3000
        let timer: ReturnType<typeof setTimeout>
        const poll = async () => {
            if (AppState.currentState === "background") {
                timer = setTimeout(poll, delay)
                return
            }
            try {
                const next = recoverLegacyCheckout.current
                    ? await submitCheckout({ order_id: orderId, payment_method: resolvedPaymentMethod }, () => active, true)
                    : await readSubmittedOrder(orderId)
                if (!active || !next) return
                recoverLegacyCheckout.current = false
                setPayment(current => mergePaymentState(current, next))
                const nextPhase = resolvePaymentPhase(next, resolvedPaymentMethod, order)
                setPhase(nextPhase)
                if (nextPhase === "failure") setErrorMessage(getPaymentStateError(next, t("payment.failureMessage")))
                if (nextPhase !== phase) return
                delay = Math.min(15000, delay + 1000)
            } catch (error) {
                if (!active) return
                if (error instanceof ApiError && error.status >= 400 && error.status < 500 && error.status !== 429) {
                    const code = (error.body as { detail?: { code?: string } } | null)?.detail?.code
                    if (code !== "settlement_pending") {
                        setErrorMessage(getErrorMessage(error, t("payment.statusCheckFailed")))
                        setPhase("failure")
                        return
                    }
                }
                delay = Math.min(30000, delay * 2)
            }
            if (active) timer = setTimeout(poll, delay)
        }
        timer = setTimeout(poll, delay)
        return () => { active = false; clearTimeout(timer) }
    }, [order, payment?.order_id, phase, resolvedPaymentMethod, t])

    useEffect(() => {
        if (phase !== "sbp") {
            setIsQrVisualReady(false)
            setIsQrImageFailed(false)
            return
        }

        setIsQrVisualReady(false)
        setIsQrImageFailed(false)
    }, [phase, payment?.order_id])

    useEffect(() => {
        setIsQrImageFailed(false)
    }, [qrSourceUri])

    useEffect(() => {
        if (phase !== "sbp" || shouldRenderQrImage) {
            return
        }
        setIsQrVisualReady(true)
    }, [phase, shouldRenderQrImage])

    useEffect(() => {
        const shouldPlayCelebrate = phase === "success" || phase === "pending"
        if (!shouldPlayCelebrate) {
            confettiProgress.stopAnimation()
            confettiProgress.setValue(0)
            setIsSuccessVisualReady(false)
            return
        }

        if (phase === "success") {
            setIsSuccessVisualReady(false)
        } else {
            setIsSuccessVisualReady(true)
        }

        confettiProgress.setValue(0)
        Animated.timing(confettiProgress, {
            toValue: 1,
            duration: 1500,
            easing: Easing.out(Easing.cubic),
            useNativeDriver: true,
        }).start()

        if (phase !== "success") {
            return
        }

        const timeoutId = setTimeout(() => {
            setIsSuccessVisualReady(true)
        }, 1200)

        return () => {
            clearTimeout(timeoutId)
        }
    }, [confettiProgress, phase])

    const renderConfettiOverlay = () => (
        <View pointerEvents="none" style={paymentScreenStyles.confettiLayer}>
            {CONFETTI_PIECES.map((piece, index) => {
                const inputStart = Math.max(0.001, piece.delay / 1500)
                const inputMid = Math.min(inputStart + 0.2, 0.85)
                const translateY = confettiProgress.interpolate({
                    inputRange: [0, inputStart, 1],
                    outputRange: [0, 0, piece.travel],
                })
                const translateX = confettiProgress.interpolate({
                    inputRange: [0, 1],
                    outputRange: [0, piece.drift],
                })
                const rotate = confettiProgress.interpolate({
                    inputRange: [0, 1],
                    outputRange: ["0deg", piece.rotation],
                })
                const opacity = confettiProgress.interpolate({
                    inputRange: [0, inputStart, inputMid, 1],
                    outputRange: [0, 0, 1, 0],
                })

                return (
                    <Animated.View
                        key={`${piece.left}-${index}`}
                        style={[
                            paymentScreenStyles.confettiPiece,
                            {
                                backgroundColor: piece.color,
                                height: piece.size * 1.6,
                                left: `${piece.left}%`,
                                opacity,
                                top: piece.top,
                                transform: [{ translateX }, { translateY }, { rotate }],
                                width: piece.size,
                            },
                        ]}
                    />
                )
            })}
        </View>
    )

    const renderVisualCard = () => {
        if (phase === "sbp") {
            return (
                <View style={[paymentScreenStyles.visualCard, paymentScreenStyles.visualCardQROnly]}>
                    <View style={[paymentScreenStyles.visualWrap, paymentScreenStyles.visualWrapQROnly]}>
                        <Pressable
                            accessibilityRole={qrLinkTarget ? "link" : "image"}
                            disabled={!qrLinkTarget}
                            onPress={openQrLink}
                            style={({ pressed }) => [
                                paymentScreenStyles.qrFrame,
                                paymentScreenStyles.qrFrameQROnly,
                                pressed && qrLinkTarget && paymentScreenStyles.qrFramePressed,
                            ]}
                        >
                            {shouldRenderQrImage ? (
                                <Image
                                    resizeMode="contain"
                                    source={qrImageSource!}
                                    style={paymentScreenStyles.qrImage}
                                    onError={() => {
                                        setIsQrImageFailed(true)
                                        setIsQrVisualReady(true)
                                    }}
                                    onLoad={() => {
                                        setIsQrImageFailed(false)
                                        setIsQrVisualReady(true)
                                    }}
                                />
                            ) : (
                                <View style={paymentScreenStyles.qrPlaceholder}>
                                    <Text style={paymentScreenStyles.qrPlaceholderText}>
                                        {qrLinkTarget ? t("payment.tapToPayPlaceholder") : t("payment.qrUnavailable")}
                                    </Text>
                                </View>
                            )}
                        </Pressable>
                    </View>
                </View>
            )
        }

        if (phase === "success") {
            const successMessage = resolvedPaymentMethod === "later"
                ? t("payment.successLaterMessage")
                : t("payment.successPaidMessage")

            return (
                <View style={paymentScreenStyles.visualCard}>
                    {renderConfettiOverlay()}
                    <View style={[paymentScreenStyles.visualWrap, paymentScreenStyles.successVisualWrap]}>
                        {STICKERS.cherryCongrats.kind === "lottie" ? (
                            <LottieView
                                autoPlay
                                loop
                                onAnimationLoaded={() => {
                                    setIsSuccessVisualReady(true)
                                }}
                                source={STICKERS.cherryCongrats.source}
                                style={paymentScreenStyles.successAnimation}
                            />
                        ) : (
                            <View style={paymentScreenStyles.visualPlaceholder} />
                        )}
                        <View style={paymentScreenStyles.successCopy}>
                            <Text style={paymentScreenStyles.successBadge}>
                                {resolvedOrderStatusLabel ?? t("payment.successEyebrow")}
                            </Text>
                            <Text style={paymentScreenStyles.successTitle}>{t("payment.successTitle")}</Text>
                            <Text style={paymentScreenStyles.successMessage}>{successMessage}</Text>
                        </View>
                    </View>
                </View>
            )
        }

        if (phase === "pending") {
            return (
                <View style={paymentScreenStyles.visualCard}>
                    {renderConfettiOverlay()}
                    <View style={[paymentScreenStyles.visualWrap, paymentScreenStyles.successVisualWrap]}>
                        {STICKERS.cherryCongrats.kind === "lottie" ? (
                            <LottieView
                                autoPlay
                                loop
                                source={STICKERS.cherryCongrats.source}
                                style={paymentScreenStyles.successAnimation}
                            />
                        ) : (
                            <View style={paymentScreenStyles.visualPlaceholder} />
                        )}
                        <View style={paymentScreenStyles.successCopy}>
                            <Text style={paymentScreenStyles.successBadge}>
                                {resolvedOrderStatusLabel ?? t("payment.pending")}
                            </Text>
                            <Text style={paymentScreenStyles.successTitle}>{t("payment.pendingLaterTitle")}</Text>
                            <Text style={paymentScreenStyles.successMessage}>{t("payment.pendingLaterMessage")}</Text>
                        </View>
                    </View>
                </View>
            )
        }

        if (phase === "failure" || phase === "waiting") {
            return (
                <View style={paymentScreenStyles.visualCard}>
                    <View style={paymentScreenStyles.failureVisualBody}>
                        <Text style={paymentScreenStyles.sectionTitle}>
                            {t(phase === "waiting" ? "payment.processingOrder" : payment?.checkout_progress === "needs_review" ? "payment.title" : "payment.failureTitle")}
                        </Text>
                        <Text style={paymentScreenStyles.stateText}>{phase === "waiting" ? resolvedOrderNumber : (payment?.checkout_progress === "needs_review" ? t("payment.checkoutReview") : errorMessage ?? t("payment.failureMessage"))}</Text>
                    </View>
                </View>
            )
        }

        return null
    }

    const renderSummaryCard = () => {
        if (!hasResolvedOrderInfo) {
            return null
        }

        const renderSectionHeader = (title: string, expanded: boolean, onPress: () => void) => (
            <Pressable
                accessibilityRole="button"
                onPress={onPress}
                style={({ pressed }) => [
                    paymentScreenStyles.sectionToggle,
                    pressed && paymentScreenStyles.sectionTogglePressed,
                ]}
            >
                <Text style={paymentScreenStyles.sectionToggleTitle}>{title}</Text>
                <Text
                    style={[
                        paymentScreenStyles.sectionToggleArrow,
                        expanded && paymentScreenStyles.sectionToggleArrowExpanded,
                    ]}
                >
                    ⌄
                </Text>
            </Pressable>
        )

        const balance = confirmedBalanceAmount(order, payment)
        const discounts = orderDiscountRows(order?.checkout_snapshot)
        const renderPriceSummary = (withDivider = true) => {
            if (!basketSubtotalLabel && !deliveryTotalLabel && !totalLabel) {
                return null
            }

            return (
                <>
                    {withDivider ? <View style={paymentScreenStyles.footerDivider} /> : null}
                    <View style={paymentScreenStyles.footerPriceColumn}>
                        {basketSubtotalLabel ? (
                            <View style={paymentScreenStyles.footerPriceRow}>
                                <Text style={paymentScreenStyles.footerPriceLabel}>{t("checkout.basketSubtotalLabel")}</Text>
                                <Text style={paymentScreenStyles.footerPriceValue}>{basketSubtotalLabel}</Text>
                            </View>
                        ) : null}
                        {deliveryTotalLabel ? (
                            <View style={paymentScreenStyles.footerPriceRow}>
                                <Text style={paymentScreenStyles.footerPriceLabel}>{t("checkout.deliveryCostLabel")}</Text>
                                <Text style={paymentScreenStyles.footerPriceValue}>{deliveryTotalLabel}</Text>
                            </View>
                        ) : null}
                        {discounts.map((discount, i) => <View key={i} style={paymentScreenStyles.footerPriceRow}>
                            <Text style={paymentScreenStyles.footerPriceLabel}>{formatAppliedDiscount(discount, t)}</Text>
                            <Text style={paymentScreenStyles.footerPriceValue}>−{formatMoney(discount.amount, order?.currency)}</Text>
                        </View>)}
                        {balance !== null ? <View style={paymentScreenStyles.footerPriceRow}>
                            <Text style={paymentScreenStyles.footerPriceLabel}>{t("checkout.invoiceBalance")}</Text>
                            <Text style={paymentScreenStyles.footerPriceValue}>−{formatMoney(balance, order?.currency)}</Text>
                        </View> : null}
                        {totalLabel ? (
                            <View style={[paymentScreenStyles.footerPriceRow, paymentScreenStyles.footerPriceRowTotal]}>
                                <Text style={paymentScreenStyles.footerPriceLabelStrong}>{t("checkout.grandTotalLabel")}</Text>
                                <Text style={paymentScreenStyles.footerPriceValueStrong}>{totalLabel}</Text>
                            </View>
                        ) : null}
                    </View>
                </>
            )
        }

        return (
            <View style={paymentScreenStyles.summaryCard}>
                <View onLayout={handleSectionLayout("items")} style={paymentScreenStyles.summarySectionCard}>
                    {renderSectionHeader(t("payment.positionsTitle"), isItemsExpanded, () => {
                        handleToggleSection("items")
                    })}
                    {isItemsExpanded ? (
                        <View style={paymentScreenStyles.sectionBody}>
                            <View style={paymentScreenStyles.footerCompositionSection}>
                                <View style={paymentScreenStyles.footerCompositionList}>
                                    {resolvedItems.map((item) => {
                                        const lineTotalLabel = formatMoney(
                                            Number(item.line_total),
                                            order?.currency ?? orderDraft?.currency ?? "RUB",
                                        )

                                        return (
                                            <View key={`${item.id}-${item.variant_id}`} style={paymentScreenStyles.footerCompositionRow}>
                                                <Image
                                                    resizeMode="cover"
                                                    source={{ uri: item.image_url }}
                                                    style={paymentScreenStyles.footerCompositionImage}
                                                />
                                                <View style={paymentScreenStyles.footerCompositionBody}>
                                                    <Text numberOfLines={1} style={paymentScreenStyles.footerCompositionTitle}>
                                                        {item.product_name}
                                                    </Text>
                                                </View>
                                                <Text style={paymentScreenStyles.footerCompositionMeta}>
                                                    {item.quantity}x
                                                </Text>
                                                <Text style={paymentScreenStyles.footerCompositionPrice}>{lineTotalLabel ?? "—"}</Text>
                                            </View>
                                        )
                                    })}
                                </View>
                                {renderPriceSummary()}
                            </View>
                        </View>
                    ) : (
                        <View style={paymentScreenStyles.sectionBody}>
                            {renderPriceSummary(false)}
                        </View>
                    )}
                </View>

                <View onLayout={handleSectionLayout("contact")} style={paymentScreenStyles.summarySectionCard}>
                    {renderSectionHeader(t("payment.contactInfoTitle"), isContactExpanded, () => {
                        handleToggleSection("contact")
                    })}
                    {isContactExpanded ? (
                        <View style={paymentScreenStyles.sectionBody}>
                            <View style={paymentScreenStyles.footerInfoCard}>
                                <View style={paymentScreenStyles.footerInfoColumn}>
                                    <View style={paymentScreenStyles.footerInfoSectionSlim}>
                                        <Text numberOfLines={1} style={paymentScreenStyles.footerPrimaryLine}>
                                            {recipientLabel}
                                        </Text>
                                        <Text numberOfLines={3} style={paymentScreenStyles.footerSecondaryLine}>
                                            {deliveryLabel}
                                        </Text>
                                    </View>
                                </View>
                            </View>
                        </View>
                    ) : null}
                </View>
            </View>
        )
    }

    const renderMissingState = () => (
        <View style={paymentScreenStyles.card}>
            <Text style={paymentScreenStyles.sectionTitle}>{t("payment.orderMissingTitle")}</Text>
            <Text style={paymentScreenStyles.stateText}>{missingStateMessage}</Text>
            <Pressable
                accessibilityRole="button"
                onPress={openCheckout}
                style={({ pressed }) => [
                    paymentScreenStyles.primaryButton,
                    pressed && paymentScreenStyles.primaryButtonPressed,
                ]}
            >
                <Text style={paymentScreenStyles.primaryButtonText}>{t("payment.backToCheckout")}</Text>
            </Pressable>
        </View>
    )

    return (
        <View style={paymentScreenStyles.container}>
            <ScrollView
                contentContainerStyle={[
                    paymentScreenStyles.content,
                    phase === "sbp" ? paymentScreenStyles.contentQROnly : null,
                ]}
                ref={scrollRef}
                style={paymentScreenStyles.scrollView}
            >
                {(error || orderLoadError) && !loading && !loadingOrder && !orderDraft && !order ? (
                    renderMissingState()
                ) : !loading && !loadingOrder && !hasResolvedOrderInfo && phase === "select" ? (
                    renderMissingState()
                ) : (
                    <>
                        {renderVisualCard()}
                        {renderSummaryCard()}
                    </>
                )}
            </ScrollView>
        </View>
    )
}
