export type CreatePaymentPayload = {
    automatic_checkout?: boolean
    order_id: number
    payment_method?: "later" | "sbp"
    accept_pending_amount?: boolean
}

export type PaymentStatusRead = {
    checkout_progress?: "processing" | "needs_review" | null
    status: string
    order_id: number
    order_code: string
    order_number: string
    payment_method: string | null
    payment_status: string | null
    payment_step: string | null
    invoice_id: string | null
    amount_rubles?: number | null
    qr_url: string | null
    qr_image: string | null
    expires_at: string | null
    is_paid: boolean
    can_retry: boolean
    awaiting_settlement?: boolean
    ms_reservation_confirmed?: boolean
}
