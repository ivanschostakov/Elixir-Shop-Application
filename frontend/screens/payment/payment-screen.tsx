import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
    ActivityIndicator,
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
import { router, useLocalSearchParams } from "expo-router"
import LottieView from "lottie-react-native"

import { stickyFooterStyles } from "@/components/footer/sticky-footer.styles"
import { useApplyScreenTemplate } from "@/components/templates/screen-template.hooks"
import { ROUTES } from "@/constants/routes"
import { STICKERS } from "@/constants/stickers"
import { useOrderDraft } from "@/hooks/order-draft/use-order-draft"
import { useAuth } from "@/providers/auth-provider"
import { useLanguage } from "@/providers/language-provider"
import {
    formatMoney,
    formatRecipientName,
    getDraftRecipient,
    getSelfRecipient,
    parseDraftId,
} from "@/screens/checkout/checkout-screen.utils"
import { paymentScreenStyles } from "@/screens/payment/payment-screen.styles"
import { createOrder, getOrder } from "@/services/api/orders"
import type { OrderItemRead, OrderRead } from "@/services/api/orders.types"
import { createPayment, getPaymentStatus } from "@/services/api/payments"
import type { PaymentStatusRead } from "@/services/api/payments.types"
import type { OrderDraftItemRead } from "@/services/api/order-drafts.types"
import { getErrorMessage } from "@/utils/errors"
import { parsePositiveRouteId } from "@/utils/route-params"

type PaymentMethod = "later" | "sbp"
type SummarySection = "contact" | "items"

const FINAL_STOP_STATUSES = new Set(["error", "canceled", "refunded", "hold", "partial"])
const PAYMENT_CHROME_TEMPLATE = { footer: "none" } as const
const CONFETTI_COLORS = ["#E94E77", "#F6C85F", "#3CAEA3", "#20639B", "#F17300", "#7B61FF"] as const
const CONFETTI_PIECES = Array.from({ length: 30 }, (_, index) => ({
    color: CONFETTI_COLORS[index % CONFETTI_COLORS.length],
    delay: (index % 6) * 24,
    drift: ((index % 7) - 3) * 12,
    left: 5 + ((index * 31) % 90),
    rotation: index % 2 === 0 ? "210deg" : "-180deg",
    size: 6 + (index % 4),
    top: -24 - (index % 5) * 10,
    travel: 260 + (index % 6) * 28,
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

function mergePaymentState(previous: PaymentStatusRead | null, next: PaymentStatusRead) {
    if (!previous || previous.order_id !== next.order_id) {
        return next
    }

    return {
        ...next,
        qr_url: next.qr_url ?? previous.qr_url,
        qr_image: next.qr_image ?? previous.qr_image,
        expires_at: next.expires_at ?? previous.expires_at,
    }
}

export default function PaymentScreen() {
    const { user } = useAuth()
    const { t } = useLanguage()
    const params = useLocalSearchParams<{ draftId?: string | string[]; paymentMethod?: string | string[]; orderId?: string | string[] }>()
    const draftId = parseDraftId(params.draftId)
    const routePaymentMethod = parsePaymentMethod(params.paymentMethod)
    const routeOrderId = parsePositiveRouteId(params.orderId)
    const { orderDraft, error, loading } = useOrderDraft(draftId)
    const [selectedMethod, setSelectedMethod] = useState<PaymentMethod>(routePaymentMethod ?? "sbp")
    const [order, setOrder] = useState<OrderRead | null>(null)
    const [payment, setPayment] = useState<PaymentStatusRead | null>(null)
    const [submitting, setSubmitting] = useState(false)
    const [phase, setPhase] = useState<"select" | "processing" | "sbp" | "success" | "failure">("select")
    const [errorMessage, setErrorMessage] = useState<string | null>(null)
    const hasAutoStartedRef = useRef(false)
    const hasLoadedOrderRef = useRef(false)
    const [loadingOrder, setLoadingOrder] = useState(false)
    const [orderLoadError, setOrderLoadError] = useState<string | null>(null)
    const [isQrVisualReady, setIsQrVisualReady] = useState(false)
    const [isSuccessVisualReady, setIsSuccessVisualReady] = useState(false)
    const [isContactExpanded, setIsContactExpanded] = useState(true)
    const [isItemsExpanded, setIsItemsExpanded] = useState(true)
    const scrollRef = useRef<ScrollView>(null)
    const confettiProgress = useRef(new Animated.Value(0)).current
    const paymentStatusRequestIdRef = useRef(0)
    const sectionPositionsRef = useRef<Record<SummarySection, number>>({
        contact: 0,
        items: 0,
    })

    const openHome = useCallback(() => {
        router.replace(ROUTES.home)
    }, [])

    const openCheckout = useCallback(() => {
        if (draftId && !order) {
            router.replace({ pathname: ROUTES.checkout, params: { draftId: String(draftId) } })
            return
        }

        openHome()
    }, [draftId, openHome, order])

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
        if (!routeOrderId || order || hasLoadedOrderRef.current) {
            return
        }

        hasLoadedOrderRef.current = true
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
                setOrderLoadError(getErrorMessage(loadError, t("payment.orderMissingMessage")))
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
        const total = order?.grand_total ?? orderDraft?.grand_total
        const currency = order?.currency ?? orderDraft?.currency
        if (!total || !currency) {
            return null
        }
        return formatMoney(Number(total), currency)
    }, [order?.currency, order?.grand_total, orderDraft?.currency, orderDraft?.grand_total])
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
    const qrSourceUri = payment?.qr_image ?? payment?.qr_url ?? null
    const qrLinkTarget = payment?.qr_url ?? payment?.qr_image ?? null
    const qrImageSource = useMemo(
        () => (qrSourceUri ? { uri: qrSourceUri, cache: "force-cache" as const } : null),
        [qrSourceUri],
    )
    const hasResolvedOrderInfo = Boolean(
        (order?.delivery_address ?? orderDraft?.delivery_address)
        && resolvedRecipient
        && resolvedItemsCount > 0,
    )
    const canContinue = hasResolvedOrderInfo && !submitting
    const canRetry = Boolean(orderDraft || order?.id || payment?.order_id) && (payment ? payment.can_retry : true)
    const missingStateMessage = orderLoadError ?? t("payment.orderMissingMessage")
    const shouldShowFooter = hasResolvedOrderInfo || loading || loadingOrder || phase === "processing" || submitting
    const recipientLabel = formatRecipientName(resolvedRecipient)
    const deliveryLabel = [
        order?.selected_delivery_service ?? orderDraft?.delivery_address?.provider,
        resolvedAddress,
    ].filter(Boolean).join(" • ") || "—"

    const openQrLink = useCallback(() => {
        if (!qrLinkTarget) {
            return
        }

        void Linking.openURL(qrLinkTarget).catch(() => undefined)
    }, [qrLinkTarget])

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

    const handleStartPayment = useCallback(async (methodOverride?: PaymentMethod) => {
        const effectiveMethod = methodOverride ?? selectedMethod
        if (!orderDraft && !order) {
            return
        }

        setSubmitting(true)
        setPhase("processing")
        setErrorMessage(null)

        try {
            let nextOrder = order
            if (!nextOrder) {
                if (!orderDraft) {
                    throw new Error(t("payment.orderMissingMessage"))
                }

                nextOrder = await createOrder({
                    draft_id: orderDraft.id,
                    payment_method: effectiveMethod,
                })
                setOrder(nextOrder)
            }

            const nextPayment = await createPayment({ order_id: nextOrder.id })
            setPayment((currentPayment) => mergePaymentState(currentPayment, nextPayment))

            if (nextPayment.is_paid || nextPayment.payment_method === "later") {
                setPhase("success")
                return
            }

            if (nextPayment.payment_status && FINAL_STOP_STATUSES.has(nextPayment.payment_status)) {
                setPhase("failure")
                setErrorMessage(getPaymentStateError(nextPayment, t("payment.failureMessage")))
                return
            }

            setPhase("sbp")
        } catch (paymentError) {
            const fallback = order ? t("payment.paymentCreateFailed") : t("payment.orderCreateFailed")
            setErrorMessage(getErrorMessage(paymentError, fallback))
            setPhase("failure")
        } finally {
            setSubmitting(false)
        }
    }, [order, orderDraft, selectedMethod, t])

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
            return {
                busy: true,
                disabled: true,
                label: !isQrVisualReady ? t("payment.processingVisual") : t("payment.awaitingPayment"),
                onPress: null as (() => void) | null,
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
                onPress: openHome,
            }
        }

        if (phase === "failure" && canRetry) {
            return {
                busy: false,
                disabled: false,
                label: t("payment.retry"),
                onPress: () => {
                    void handleStartPayment(selectedMethod)
                },
            }
        }

        if (phase === "failure") {
            return {
                busy: false,
                disabled: false,
                label: t("payment.goHome"),
                onPress: openHome,
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
        handleStartPayment,
        isQrVisualReady,
        loading,
        loadingOrder,
        openHome,
        order,
        phase,
        isSuccessVisualReady,
        resolvedPaymentMethod,
        selectedMethod,
        submitting,
        t,
    ])

    const headerTitle = resolvedOrderNumber ? `#${resolvedOrderNumber}` : t("payment.title")

    const paymentChromeTemplate = useMemo(() => {
        if (!shouldShowFooter) {
            return {
                ...PAYMENT_CHROME_TEMPLATE,
                title: headerTitle,
            }
        }

        return {
            footer: "nav+customAction" as const,
            title: headerTitle,
            slots: {
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
        headerTitle,
        shouldShowFooter,
    ])

    useApplyScreenTemplate("feed", paymentChromeTemplate)

    useEffect(() => {
        if (routeOrderId || order || hasAutoStartedRef.current || phase !== "select" || loading || loadingOrder || !canContinue) {
            return
        }

        hasAutoStartedRef.current = true
        void handleStartPayment(routePaymentMethod ?? selectedMethod)
    }, [canContinue, handleStartPayment, loading, loadingOrder, order, phase, routeOrderId, routePaymentMethod, selectedMethod])

    useEffect(() => {
        if (!order?.id || payment || submitting || phase !== "select") {
            return
        }

        const paymentMethod = (order.payment_method || "").toLowerCase()
        if (paymentMethod === "later") {
            if (order.payment_status === "pending") {
                setPhase("success")
            }
            return
        }

        if (paymentMethod !== "sbp") {
            return
        }

        if (order.is_paid || order.payment_status === "paid") {
            setPhase("success")
            setErrorMessage(null)
            return
        }

        if (order.payment_status && FINAL_STOP_STATUSES.has(order.payment_status)) {
            setPhase("failure")
            setErrorMessage(getPaymentStateError(
                {
                    status: "success",
                    order_id: order.id,
                    order_code: order.order_code,
                    order_number: order.order_number,
                    payment_method: order.payment_method,
                    payment_status: order.payment_status,
                    payment_step: null,
                    invoice_id: order.payment_invoice_id,
                    qr_url: null,
                    qr_image: null,
                    expires_at: null,
                    is_paid: order.is_paid,
                    can_retry: order.payment_status === "canceled" || order.payment_status === "error",
                },
                t("payment.failureMessage"),
            ))
            return
        }

        const requestId = paymentStatusRequestIdRef.current + 1
        paymentStatusRequestIdRef.current = requestId
        setPhase("processing")
        setErrorMessage(null)

        void (async () => {
            try {
                const nextPayment = await getPaymentStatus(order.id)
                if (paymentStatusRequestIdRef.current !== requestId) {
                    return
                }
                setPayment((currentPayment) => mergePaymentState(currentPayment, nextPayment))

                if (nextPayment.is_paid || nextPayment.payment_status === "paid") {
                    setPhase("success")
                    return
                }

                if (nextPayment.payment_status && FINAL_STOP_STATUSES.has(nextPayment.payment_status)) {
                    setPhase("failure")
                    setErrorMessage(getPaymentStateError(nextPayment, t("payment.failureMessage")))
                    return
                }

                setPhase("sbp")
            } catch (resumeError) {
                if (paymentStatusRequestIdRef.current !== requestId) {
                    return
                }
                setPhase("failure")
                setErrorMessage(getErrorMessage(resumeError, t("payment.statusCheckFailed")))
            }
        })()
    }, [order, payment, phase, submitting, t])

    useEffect(() => {
        if (phase !== "sbp" || !payment?.order_id) {
            return
        }

        const intervalId = setInterval(() => {
            void (async () => {
                try {
                    const nextPayment = await getPaymentStatus(payment.order_id)
                    setPayment((currentPayment) => mergePaymentState(currentPayment, nextPayment))

                    if (nextPayment.is_paid || nextPayment.payment_status === "paid") {
                        setPhase("success")
                        setErrorMessage(null)
                        return
                    }

                    if (nextPayment.payment_status && FINAL_STOP_STATUSES.has(nextPayment.payment_status)) {
                        setPhase("failure")
                        setErrorMessage(getPaymentStateError(nextPayment, t("payment.failureMessage")))
                    }
                } catch (pollError) {
                    setErrorMessage(getErrorMessage(pollError, t("payment.statusCheckFailed")))
                }
            })()
        }, 4000)

        return () => {
            clearInterval(intervalId)
        }
    }, [payment?.order_id, phase, t])

    useEffect(() => {
        if (phase !== "sbp") {
            setIsQrVisualReady(false)
            return
        }

        setIsQrVisualReady(false)
    }, [phase, payment?.order_id])

    useEffect(() => {
        if (phase !== "success") {
            setIsSuccessVisualReady(false)
            return
        }

        setIsSuccessVisualReady(false)
        confettiProgress.setValue(0)
        Animated.timing(confettiProgress, {
            toValue: 1,
            duration: 1500,
            easing: Easing.out(Easing.cubic),
            useNativeDriver: true,
        }).start()
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
                            {qrImageSource ? (
                                <Image
                                    resizeMode="contain"
                                    source={qrImageSource}
                                    style={paymentScreenStyles.qrImage}
                                    onError={() => {
                                        setIsQrVisualReady(true)
                                    }}
                                    onLoad={() => {
                                        setIsQrVisualReady(true)
                                    }}
                                />
                            ) : (
                                <View style={paymentScreenStyles.visualPlaceholder} />
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
                                loop={false}
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
                            <Text style={paymentScreenStyles.successBadge}>{t("payment.successEyebrow")}</Text>
                            <Text style={paymentScreenStyles.successTitle}>{t("payment.successTitle")}</Text>
                            <Text style={paymentScreenStyles.successMessage}>{successMessage}</Text>
                            {resolvedOrderNumber ? (
                                <View style={paymentScreenStyles.successOrderBox}>
                                    <Text style={paymentScreenStyles.successOrderLabel}>{t("payment.orderNumber")}</Text>
                                    <Text style={paymentScreenStyles.successOrderValue}>#{resolvedOrderNumber}</Text>
                                </View>
                            ) : null}
                        </View>
                    </View>
                </View>
            )
        }

        if (phase === "failure") {
            return (
                <View style={paymentScreenStyles.visualCard}>
                    <View style={paymentScreenStyles.failureVisualBody}>
                        <Text style={paymentScreenStyles.sectionTitle}>{t("payment.failureTitle")}</Text>
                        <Text style={paymentScreenStyles.stateText}>{errorMessage ?? t("payment.failureMessage")}</Text>
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
                ) : !loading && !loadingOrder && !hasResolvedOrderInfo ? (
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
