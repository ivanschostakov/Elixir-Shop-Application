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

export function resolvePaymentPhase(payment: PaymentStatusRead, requestedMethod: PaymentMethod) {
    if (payment.payment_status && FINAL_STOP_STATUSES.has(payment.payment_status)) return "failure"
    if (payment.is_paid || payment.payment_status === "paid") return "success"
    if (payment.payment_method === "later" && payment.ms_reservation_confirmed === true && payment.invoice_ready !== false) return "pending"
    if (!payment.invoice_id && (payment.payment_status === "draft" || payment.awaiting_settlement || payment.invoice_ready === false)) return "waiting"
    const method = payment.payment_method === "later" || payment.payment_method === "sbp"
        ? payment.payment_method
        : requestedMethod
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
