import { useAsyncData } from "@/hooks/shared/use-async-data"
import { getBanners } from "@/services/api/banners"
import type { Banner } from "@/types/banner"

export function useBanners(enabled = true) {
    const { data: banners, error, loading } = useAsyncData<Banner[]>({
        deps: [],
        enabled,
        fetcher: () => getBanners({ limit: 1, sort: "priority_desc" }),
        initialData: [],
    })

    return { banners, error, loading }
}
