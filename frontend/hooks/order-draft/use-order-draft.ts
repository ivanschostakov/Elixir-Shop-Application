import { useEffect } from "react"

import { subscribeOrderDraftSnapshot, getOrderDraftSnapshot, setOrderDraftSnapshot } from "@/hooks/order-draft/order-draft-store"
import { useAsyncData } from "@/hooks/shared/use-async-data"
import { ApiError } from "@/services/api/client"
import { getLatestOrderDraft, getOrderDraft } from "@/services/api/order-drafts"
import type { OrderDraftRead } from "@/services/api/order-drafts.types"
import type { UseOrderDraftResult } from "@/hooks/order-draft/use-order-draft.types"

function getInitialOrderDraft(draftId: number | null) {
    const snapshot = getOrderDraftSnapshot()
    if (!snapshot) {
        return null
    }

    if (draftId !== null && snapshot.id !== draftId) {
        return null
    }

    return snapshot
}

export function useOrderDraft(draftId: number | null): UseOrderDraftResult {
    const { data: orderDraft, error, loading, reload, setData } = useAsyncData<OrderDraftRead | null>({
        deps: [draftId],
        fetcher: async () => {
            try {
                const nextOrderDraft = draftId === null
                    ? await getLatestOrderDraft()
                    : await getOrderDraft(draftId)

                setOrderDraftSnapshot(nextOrderDraft)
                return nextOrderDraft
            } catch (loadError) {
                if (loadError instanceof ApiError && loadError.status === 404) {
                    setOrderDraftSnapshot(null)
                    return null
                }

                throw loadError
            }
        },
        initialData: getInitialOrderDraft(draftId),
    })

    useEffect(() => subscribeOrderDraftSnapshot(setData), [setData])

    return {
        orderDraft,
        error,
        loading,
        reload: async () => {
            const nextOrderDraft = await reload()
            return nextOrderDraft
        },
    }
}
