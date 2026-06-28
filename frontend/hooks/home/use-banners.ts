import { useAsyncData } from "@/hooks/shared/use-async-data"
import { getBanners } from "@/services/api/banners"
import type { Banner } from "@/types/banner"

const ACTIVE_BANNERS_LIMIT = 50

export function useBanners(enabled = true) {
    const { data: banners, error, loading, reload } = useAsyncData<Banner[]>({
        deps: [],
        enabled,
        fetcher: () => getBanners({ limit: ACTIVE_BANNERS_LIMIT, sort: "priority_desc" }),
        initialData: [],
    })

    return { banners, error, loading, reload }
}
