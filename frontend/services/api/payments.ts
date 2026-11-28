import { ApiError, apiGet, apiPost } from "@/services/api/client"
import { ENDPOINTS } from "@/services/api/constants"
import { REQUEST_TIMEOUT_MS } from "@/services/api/request-deadline"
import type { CreatePaymentPayload, PaymentStatusRead } from "@/services/api/payments.types"

const paymentsEndpoint = ENDPOINTS.PAYMENTS

export class PaymentPreparationPendingError extends Error {}

export function createPayment(payload: CreatePaymentPayload, timeoutMs = REQUEST_TIMEOUT_MS): Promise<PaymentStatusRead> {
    return apiPost<PaymentStatusRead, CreatePaymentPayload>(`${paymentsEndpoint}/create`, payload, { appIntegrityAction: "payments:create", timeoutMs })
}

export async function createPaymentWhenReady(
    payload: CreatePaymentPayload,
    { isActive, onPending, timeoutMessage, checkFirst = false, retryExport = false }: {
        isActive: () => boolean
        onPending: () => void
        timeoutMessage: string
        checkFirst?: boolean
        retryExport?: boolean
    },
): Promise<PaymentStatusRead | null> {
    if (!isActive()) return null
    const deadline = Date.now() + REQUEST_TIMEOUT_MS
    const remaining = () => {
        const ms = deadline - Date.now()
        if (ms <= 0) throw new PaymentPreparationPendingError(timeoutMessage)
        return ms
    }
    try {
        if (checkFirst) {
            const state = await getPaymentStatus(payload.order_id, true, remaining())
            if (!isActive()) return null
            if (state.is_paid || state.invoice_id || ["paid", "refunded", "canceled", "error", "partial", "hold"].includes(state.payment_status ?? "")) return state
            if (state.invoice_ready === false) {
                if (retryExport && state.export_retry_available) {
                    await createPayment({ ...payload, retry_export: true }, remaining())
                }
                onPending()
                throw new PaymentPreparationPendingError(timeoutMessage)
            }
            if (payload.payment_method !== "later" && state.invoice_ready !== true && !state.awaiting_settlement && state.payment_status !== "draft") return state
        }
        const payment = await createPayment(payload, remaining())
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

export function getPaymentStatus(orderId: number, checkInvoice = false, timeoutMs = REQUEST_TIMEOUT_MS): Promise<PaymentStatusRead> {
    return apiGet<PaymentStatusRead>(`${paymentsEndpoint}/status`, { order_id: orderId, ...(checkInvoice ? { check_invoice: true } : {}) }, { appIntegrityAction: "payments:status", timeoutMs })
}
