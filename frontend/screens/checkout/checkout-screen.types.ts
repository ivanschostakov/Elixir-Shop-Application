import type {
    DeliveryRecipientRead,
    OrderDraftRead,
} from "@/services/api/order-drafts.types"

export type ExpandedSection = "recipient" | "address" | null

export type LegacyOrderDraftRecipientFields = {
    recipient?: DeliveryRecipientRead | null
    recipient_id?: number | null
    recipient_name?: string | null
    recipient_phone?: string | null
    recipient_email?: string | null
}

export type RecipientFormState = {
    firstName: string
    lastName: string
    phone: string
    email: string
}

export type RecipientFormErrors = Partial<Record<keyof RecipientFormState, string>>

export type OrderDraftWithLegacyRecipientFields = OrderDraftRead & LegacyOrderDraftRecipientFields
