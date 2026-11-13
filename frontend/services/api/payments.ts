import { ApiError, apiGet, apiPost } from "@/services/api/client"
import { ENDPOINTS } from "@/services/api/constants"
import type { CreatePaymentPayload, PaymentStatusRead } from "@/services/api/payments.types"

const paymentsEndpoint = ENDPOINTS.PAYMENTS

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
    const deadline = Date.now() + 120_000
    while (isActive()) {
        try {
            const payment = await createPayment(payload)
            return isActive() ? payment : null
        } catch (error) {
            if (!isActive()) return null
            const detail = error instanceof ApiError && error.status === 409
                ? (error.body as { detail?: { code?: string } } | null)?.detail
                : null
            // Only this response guarantees that this request did not start a payment.
            if (detail?.code !== "settlement_pending") throw error
            if (Date.now() >= deadline) throw new Error(timeoutMessage)
            onPending()
            await new Promise((resolve) => setTimeout(resolve, 4_000))
        }
    }
    return null
}

export function getPaymentStatus(orderId: number): Promise<PaymentStatusRead> {
    return apiGet<PaymentStatusRead>(`${paymentsEndpoint}/status`, { order_id: orderId }, { appIntegrityAction: "payments:status" })
}
