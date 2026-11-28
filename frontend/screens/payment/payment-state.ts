import type { PaymentStatusRead } from "@/services/api/payments.types"
import type { OrderRead } from "@/services/api/orders.types"

type PaymentMethod = "later" | "sbp"

const FINAL_STOP_STATUSES = new Set(["error", "canceled", "refunded", "hold", "partial"])

export function confirmedPaidOrderId(userId: number | undefined, order: OrderRead | null, payment: PaymentStatusRead | null) {
    if (!order || userId !== order.user_id || (payment && payment.order_id !== order.id)) return null
    const status = payment ?? order
    if (FINAL_STOP_STATUSES.has(status.payment_status ?? "")) return null
    return status.is_paid || status.payment_status === "paid" ? order.id : null
}

export function laterCheckoutState(order: OrderRead | null, payment: PaymentStatusRead | null = null) {
    if (!order || order.checkout_snapshot?.ms_checkout_version !== 2 || order.payment_method !== "later"
        || order.is_canceled || order.is_paid || !["draft", "pending"].includes(order.payment_status)) return null
    const current = payment?.order_id === order.id ? payment : null
    if (current?.is_paid || (current?.payment_status && FINAL_STOP_STATUSES.has(current.payment_status))) return null
    if ((current ? current.ms_reservation_confirmed : order.ms_reservation_confirmed) !== true) return "reserving"
    const settlement = order.checkout_snapshot.settlement_payment as { status?: string } | undefined
    if (current ? current.awaiting_settlement : settlement && settlement.status !== "confirmed") return "calculating"
    return "ready"
}

export function visibleOrderTotal(order: OrderRead | null, payment: PaymentStatusRead | null = null) {
    if (!order) return null
    const current = payment?.order_id === order.id ? payment : null
    const state = laterCheckoutState(order, current)
    if (state === "reserving" || state === "calculating" || current?.awaiting_settlement) return null
    const settlement = order.checkout_snapshot?.settlement_payment as { status?: string } | undefined
    if (settlement && settlement.status !== "confirmed" && current?.amount_rubles == null) return null
    return current?.amount_rubles ?? order.grand_total
}

export function resolvePaymentPhase(payment: PaymentStatusRead, requestedMethod: PaymentMethod, order: OrderRead | null = null) {
    if (order?.is_canceled) return "failure"
    if (payment.payment_status && FINAL_STOP_STATUSES.has(payment.payment_status)) return "failure"
    if (payment.is_paid || payment.payment_status === "paid") return "success"
    const method = payment.payment_method === "later" || payment.payment_method === "sbp"
        ? payment.payment_method
        : requestedMethod
    if (method === "later" && laterCheckoutState(order, payment) === "reserving") return "waiting"
    return method === "later" ? "pending" : "sbp"
}

export function mergePaymentState(previous: PaymentStatusRead | null, next: PaymentStatusRead) {
    if (!previous || previous.order_id !== next.order_id || previous.invoice_id !== next.invoice_id) {
        return next
    }
    return {
        ...next,
        qr_url: next.qr_url ?? previous.qr_url,
        qr_image: next.qr_image ?? previous.qr_image,
        expires_at: next.expires_at ?? previous.expires_at,
    }
}
