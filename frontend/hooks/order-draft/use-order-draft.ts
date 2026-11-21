import { useEffect } from "react"

import { subscribeOrderDraftSnapshot, getOrderDraftSnapshot, setOrderDraftSnapshot } from "@/hooks/order-draft/order-draft-store"
import { useAsyncData } from "@/hooks/shared/use-async-data"
import { ApiError } from "@/services/api/client"
import { getOrderDraft } from "@/services/api/order-drafts"
import type { OrderDraftRead } from "@/services/api/order-drafts.types"
import type { UseOrderDraftResult } from "@/hooks/order-draft/use-order-draft.types"
import { useAuth } from "@/providers/auth-provider.context"
import { commerceAccountRevision } from "@/services/commerce-account"

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
    const { user } = useAuth()
    const { data: orderDraft, error, loading, reload, setData } = useAsyncData<OrderDraftRead | null>({
        deps: [user?.id ?? null, draftId],
        fetcher: async () => {
            const revision = commerceAccountRevision()
            if (draftId === null) {
                setOrderDraftSnapshot(null)
                return null
            }

            try {
                const nextOrderDraft = await getOrderDraft(draftId)

                if (commerceAccountRevision() === revision) setOrderDraftSnapshot(nextOrderDraft)
                return nextOrderDraft
            } catch (loadError) {
                if (loadError instanceof ApiError && loadError.status === 404) {
                    if (commerceAccountRevision() === revision) setOrderDraftSnapshot(null)
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
