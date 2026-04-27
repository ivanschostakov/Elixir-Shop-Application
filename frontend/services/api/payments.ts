import { apiGet, apiPost } from "@/services/api/client"
import { ENDPOINTS } from "@/services/api/constants"
import type { CreatePaymentPayload, PaymentStatusRead } from "@/services/api/payments.types"

const paymentsEndpoint = ENDPOINTS.PAYMENTS

export function createPayment(payload: CreatePaymentPayload): Promise<PaymentStatusRead> {
    return apiPost<PaymentStatusRead, CreatePaymentPayload>(`${paymentsEndpoint}/create`, payload)
}

export function getPaymentStatus(orderId: number): Promise<PaymentStatusRead> {
    return apiGet<PaymentStatusRead>(`${paymentsEndpoint}/status`, { order_id: orderId })
}
