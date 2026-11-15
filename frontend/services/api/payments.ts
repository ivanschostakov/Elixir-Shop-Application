import { ApiError, apiGet, apiPost } from "@/services/api/client"
import { ENDPOINTS } from "@/services/api/constants"
import type { CreatePaymentPayload, PaymentStatusRead } from "@/services/api/payments.types"

const paymentsEndpoint = ENDPOINTS.PAYMENTS
const PAYMENT_PREPARATION_TIMEOUT_MS = 180_000

export class PaymentPreparationPendingError extends Error {}

export function createPayment(payload: CreatePaymentPayload): Promise<PaymentStatusRead> {
    return apiPost<PaymentStatusRead, CreatePaymentPayload>(`${paymentsEndpoint}/create`, payload, { appIntegrityAction: "payments:create" })
}

export async function createPaymentWhenReady(
    payload: CreatePaymentPayload,
    { isActive, onPending, timeoutMessage }: {
        isActive: () => boolean
        onPending: () => void
        timeoutMessage: string
    },
): Promise<PaymentStatusRead | null> {
    const deadline = Date.now() + PAYMENT_PREPARATION_TIMEOUT_MS
    while (isActive()) {
        try {
            const payment = await createPayment(payload)
            return isActive() ? payment : null
        } catch (error) {
            if (!isActive()) return null
            const detail = error instanceof ApiError && error.status === 409
                ? (error.body as { detail?: { code?: string; retry_after_seconds?: number } } | null)?.detail
                : null
            // Only this response guarantees that this request did not start a payment.
            if (detail?.code !== "settlement_pending") throw error
            const timeLeft = deadline - Date.now()
            if (timeLeft <= 0) throw new PaymentPreparationPendingError(timeoutMessage)
            onPending()
            const retryDelay = typeof detail.retry_after_seconds === "number" && Number.isFinite(detail.retry_after_seconds)
                ? Math.max(4_000, detail.retry_after_seconds * 1_000)
                : 4_000
            await new Promise((resolve) => setTimeout(resolve, Math.min(retryDelay, timeLeft)))
            if (isActive() && Date.now() >= deadline) throw new PaymentPreparationPendingError(timeoutMessage)
        }
    }
    return null
}

export function getPaymentStatus(orderId: number): Promise<PaymentStatusRead> {
    return apiGet<PaymentStatusRead>(`${paymentsEndpoint}/status`, { order_id: orderId }, { appIntegrityAction: "payments:status" })
}
