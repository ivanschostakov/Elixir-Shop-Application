import type { OrderDraftRead } from "@/services/api/order-drafts.types"

export type RecentOrderDraftsRailProps = {
    drafts: OrderDraftRead[]
}

export type RecentOrderDraftCardProps = {
    draft: OrderDraftRead
    onDraftUpdated: (draft: OrderDraftRead) => void
    onDraftDeleted: (draftId: number) => void
}
