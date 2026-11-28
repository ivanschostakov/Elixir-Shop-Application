import { ApiError, apiGet, apiPost } from "@/services/api/client"
import { ENDPOINTS } from "@/services/api/constants"
import type { CreatePaymentPayload, PaymentStatusRead } from "@/services/api/payments.types"

const paymentsEndpoint = ENDPOINTS.PAYMENTS

export class PaymentPreparationPendingError extends Error {}

export function createPayment(payload: CreatePaymentPayload): Promise<PaymentStatusRead> {
    return apiPost<PaymentStatusRead, CreatePaymentPayload>(`${paymentsEndpoint}/create`, payload, { appIntegrityAction: "payments:create" })
}

export async function createPaymentWhenReady(
    payload: CreatePaymentPayload,
    { isActive, onPending, timeoutMessage, checkFirst = false }: {
        isActive: () => boolean
        onPending: () => void
        timeoutMessage: string
        checkFirst?: boolean
    },
): Promise<PaymentStatusRead | null> {
    if (!isActive()) return null
    try {
        if (checkFirst) {
            const state = await getPaymentStatus(payload.order_id, true)
            if (!isActive()) return null
            if (state.is_paid || state.invoice_id || ["paid", "refunded", "canceled", "error", "partial", "hold"].includes(state.payment_status ?? "")) return state
            if (state.invoice_ready === false) {
                onPending()
                throw new PaymentPreparationPendingError(timeoutMessage)
            }
            if (state.invoice_ready !== true && !state.awaiting_settlement && state.payment_status !== "draft") return state
        }
        const payment = await createPayment(payload)
        return isActive() ? payment : null
    } catch (error) {
        if (!isActive()) return null
        const detail = error instanceof ApiError && error.status === 409
            ? (error.body as { detail?: { code?: string } } | null)?.detail : null
        if (detail?.code !== "settlement_pending") throw error
        onPending()
        throw new PaymentPreparationPendingError(timeoutMessage)
    }
}

export function getPaymentStatus(orderId: number, checkInvoice = false): Promise<PaymentStatusRead> {
    return apiGet<PaymentStatusRead>(`${paymentsEndpoint}/status`, { order_id: orderId, ...(checkInvoice ? { check_invoice: true } : {}) }, { appIntegrityAction: "payments:status" })
}
