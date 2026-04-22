import type { OrderDraftRead } from "@/services/api/order-drafts.types"

export type UseOrderDraftResult = {
    orderDraft: OrderDraftRead | null
    error: string | null
    loading: boolean
    reload: () => Promise<OrderDraftRead | null>
}
