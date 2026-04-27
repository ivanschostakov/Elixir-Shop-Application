import { useAsyncData } from "@/hooks/shared/use-async-data"
import { getOrderDrafts } from "@/services/api/order-drafts"
import type { OrderDraftRead } from "@/services/api/order-drafts.types"

type UseRecentOrderDraftsResult = {
    orderDrafts: OrderDraftRead[]
    error: string | null
    loading: boolean
    reload: () => Promise<OrderDraftRead[] | null>
}

export function useRecentOrderDrafts(limit = 6): UseRecentOrderDraftsResult {
    const { data, error, loading, reload } = useAsyncData<OrderDraftRead[]>({
        deps: [limit],
        fetcher: () => getOrderDrafts({ limit }),
        initialData: [],
    })

    return {
        orderDrafts: data,
        error,
        loading,
        reload,
    }
}
