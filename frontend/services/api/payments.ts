import { ApiError, apiGet, apiPost } from "@/services/api/client"
import { ENDPOINTS } from "@/services/api/constants"
import { REQUEST_TIMEOUT_MS } from "@/services/api/request-deadline"
import type { CreatePaymentPayload, PaymentStatusRead } from "@/services/api/payments.types"

const paymentsEndpoint = ENDPOINTS.PAYMENTS
type CheckoutRequest = Pick<CreatePaymentPayload, "order_id" | "payment_method">

export function readSubmittedOrder(orderId: number): Promise<PaymentStatusRead> {
    return apiGet<PaymentStatusRead>(`${paymentsEndpoint}/status`,
        { order_id: orderId, automatic_checkout: true, accept_pending_amount: true },
        { appIntegrityAction: "payments:status" })
}

// Only a reopened order can adopt an unscheduled legacy draft.
async function readCheckoutForResume(orderId: number): Promise<PaymentStatusRead | null> {
    try {
        const state = await readSubmittedOrder(orderId)
        if (state.status_code || state.checkout_issue || state.checkout_progress ||
            state.invoice_id || state.qr_url || state.qr_image || state.is_paid ||
            !["draft", "pending"].includes(state.payment_status ?? "") ||
            (state.payment_method === "later" && state.ms_reservation_confirmed)) return state
    } catch (error) {
        if (!isSettlementPending(error)) throw error
    }
    return null
}

export async function submitCheckout(payload: CheckoutRequest, active: () => boolean, resume = false, onResumeRead?: () => void): Promise<PaymentStatusRead | null> {
    if (!active()) return null
    if (resume) {
        const existing = await readCheckoutForResume(payload.order_id)
        if (!active()) return null
        onResumeRead?.()
        if (existing) return existing
    }
    const result = await createPayment({ ...payload, automatic_checkout: true })
    return active() ? result : null
}

export class PaymentPreparationPendingError extends Error {}

export function createPayment(payload: CreatePaymentPayload, timeoutMs = REQUEST_TIMEOUT_MS): Promise<PaymentStatusRead> {
    const body = payload.payment_method === "later" ? { ...payload, accept_pending_amount: true } : payload
    return apiPost<PaymentStatusRead, CreatePaymentPayload>(`${paymentsEndpoint}/create`, body, { appIntegrityAction: "payments:create", timeoutMs })
}

function isSettlementPending(error: unknown) {
    return error instanceof ApiError && error.status === 409 &&
        (error.body as { detail?: { code?: string } } | null)?.detail?.code === "settlement_pending"
}

// Legacy readiness interface. Never poll or repeat a POST; current checkout uses the worker.
export async function createPaymentWhenReady(
    payload: CheckoutRequest,
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
            if (state.checkout_progress || state.checkout_issue || state.status_code === "processing" || state.status_code === "checkout_failed" ||
                state.is_paid || state.invoice_id || state.qr_url || state.qr_image || ["paid", "refunded", "canceled", "error", "partial", "hold"].includes(state.payment_status ?? "")) return state
            if (payload.payment_method === "later" && state.payment_method === "later" && state.ms_reservation_confirmed && state.payment_status === "pending" && state.invoice_ready !== false) return state
            if (state.invoice_ready === false) {
                if (retryExport && state.export_retry_available) {
                    await createPayment({ ...payload, retry_export: true }, remaining())
                    if (!isActive()) return null
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
        if (!isSettlementPending(error)) throw error
        onPending()
        throw new PaymentPreparationPendingError(timeoutMessage)
    }
}

export function getPaymentStatus(orderId: number, checkInvoice = false, timeoutMs = REQUEST_TIMEOUT_MS, acceptPendingAmount = !checkInvoice): Promise<PaymentStatusRead> {
    return apiGet<PaymentStatusRead>(`${paymentsEndpoint}/status`, { order_id: orderId, ...(checkInvoice ? { check_invoice: true } : {}), ...(acceptPendingAmount ? { accept_pending_amount: true } : {}) }, { appIntegrityAction: "payments:status", timeoutMs })
}
