import { useAsyncData } from "@/hooks/shared/use-async-data"
import { getRequisites } from "@/services/api/requisites"
import type { RequisiteRead } from "@/types/requisite"

export function useRequisites(enabled = true) {
    const { data: requisites, error, loading, reload } = useAsyncData<RequisiteRead[]>({
        deps: [],
        enabled,
        fetcher: getRequisites,
        initialData: [],
    })

    return {
        requisites,
        error,
        loading,
        reload,
    }
}
