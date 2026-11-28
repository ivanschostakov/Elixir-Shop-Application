import { ApiError, apiGet, apiPost } from "@/services/api/client"
import { ENDPOINTS } from "@/services/api/constants"
import { REQUEST_TIMEOUT_MS } from "@/services/api/request-deadline"
import type { CreatePaymentPayload, PaymentStatusRead } from "@/services/api/payments.types"

const paymentsEndpoint = ENDPOINTS.PAYMENTS

export class PaymentPreparationPendingError extends Error {}

export function createPayment(payload: CreatePaymentPayload, timeoutMs = REQUEST_TIMEOUT_MS): Promise<PaymentStatusRead> {
    const body = payload.payment_method === "later" ? { ...payload, accept_pending_amount: true } : payload
    return apiPost<PaymentStatusRead, CreatePaymentPayload>(`${paymentsEndpoint}/create`, body, { appIntegrityAction: "payments:create", timeoutMs })
}

function pendingDetail(error: unknown) {
    if (!(error instanceof ApiError) || error.status !== 409) return null
    const detail = (error.body as { detail?: { code?: string; retry_after_seconds?: number } } | null)?.detail
    return detail?.code === "settlement_pending" ? detail : null
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
            const state = await getPaymentStatus(payload.order_id, true, remaining(), payload.payment_method === "later")
            if (!isActive()) return null
            if (state.is_paid || state.invoice_id || ["paid", "refunded", "canceled", "error", "partial", "hold"].includes(state.payment_status ?? "")) return state
            if (payload.payment_method === "later" && state.payment_method === "later" && state.ms_reservation_confirmed && state.payment_status === "pending" && state.invoice_ready !== false) return state
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
        let detail = pendingDetail(error)
        if (!detail) throw error
        onPending()
        while (payload.payment_method === "later" && isActive()) {
            const retryMs = Number(detail?.retry_after_seconds) * 1000
            await new Promise(resolve => setTimeout(resolve, Math.min(remaining(), Math.max(4000, Number.isFinite(retryMs) ? retryMs : 4000))))
            if (!isActive()) return null
            try {
                const state = await getPaymentStatus(payload.order_id, true, remaining(), true)
                if (!isActive()) return null
                if ((state.ms_reservation_confirmed && state.payment_method === "later" && state.invoice_ready !== false) || state.is_paid ||
                    ["paid", "refunded", "canceled", "error", "partial", "hold"].includes(state.payment_status ?? "")) return state
                if (state.ms_reservation_confirmed === undefined) break
            } catch (pollError) {
                if (!isActive()) return null
                detail = pendingDetail(pollError)
                if (!detail) throw pollError
            }
        }
        throw new PaymentPreparationPendingError(timeoutMessage)
    }
}

export function getPaymentStatus(orderId: number, checkInvoice = false, timeoutMs = REQUEST_TIMEOUT_MS, acceptPendingAmount = false): Promise<PaymentStatusRead> {
    return apiGet<PaymentStatusRead>(`${paymentsEndpoint}/status`, { order_id: orderId, ...(checkInvoice ? { check_invoice: true } : {}), ...(acceptPendingAmount ? { accept_pending_amount: true } : {}) }, { appIntegrityAction: "payments:status", timeoutMs })
}
