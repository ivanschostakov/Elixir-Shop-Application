export type CreatePaymentPayload = {
    order_id: number
}

export type PaymentStatusRead = {
    status: string
    order_id: number
    order_code: string
    order_number: string
    payment_method: string | null
    payment_status: string | null
    payment_step: string | null
    invoice_id: string | null
    qr_url: string | null
    qr_image: string | null
    expires_at: string | null
    is_paid: boolean
    can_retry: boolean
}
