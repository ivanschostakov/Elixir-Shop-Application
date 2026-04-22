import type { OrderDraftRead } from "@/services/api/order-drafts.types"

type OrderDraftTitleSource = Pick<OrderDraftRead, "id" | "created_at" | "draft_name">

function formatOrderDraftDate(createdAt: string) {
    try {
        return new Intl.DateTimeFormat("ru-RU", {
            day: "2-digit",
            month: "2-digit",
            year: "2-digit",
        }).format(new Date(createdAt))
    } catch {
        return null
    }
}

export function getOrderDraftTitle(orderDraft: OrderDraftTitleSource) {
    if (orderDraft.draft_name) {
        return orderDraft.draft_name
    }

    const formattedDate = formatOrderDraftDate(orderDraft.created_at)
    return formattedDate
        ? `#${orderDraft.id} от ${formattedDate}`
        : `#${orderDraft.id}`
}
