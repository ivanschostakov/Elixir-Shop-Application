import { useSyncExternalStore } from "react"

import type { OrderDraftRead } from "@/services/api/order-drafts.types"

type OrderDraftListener = (orderDraft: OrderDraftRead | null) => void

let orderDraftSnapshot: OrderDraftRead | null = null

const listeners = new Set<OrderDraftListener>()

export function getOrderDraftSnapshot() {
    return orderDraftSnapshot
}

export function setOrderDraftSnapshot(nextOrderDraft: OrderDraftRead | null) {
    orderDraftSnapshot = nextOrderDraft
    listeners.forEach((listener) => listener(nextOrderDraft))
}

export function clearOrderDraftSnapshot() {
    setOrderDraftSnapshot(null)
}

export function subscribeOrderDraftSnapshot(listener: OrderDraftListener) {
    listeners.add(listener)

    return () => {
        listeners.delete(listener)
    }
}

export function useOrderDraftSnapshot() {
    return useSyncExternalStore(
        subscribeOrderDraftSnapshot,
        getOrderDraftSnapshot,
        () => null,
    )
}
