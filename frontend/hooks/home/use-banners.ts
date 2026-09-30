import { useAsyncData } from "@/hooks/shared/use-async-data"
import { getBanners } from "@/services/api/banners"
import { useAuth } from "@/providers/auth-provider"
import type { Banner } from "@/types/banner"

const ACTIVE_BANNERS_LIMIT = 50

export function useBanners(enabled = true) {
    const { user, isReady } = useAuth()
    const { data: banners, error, loading, reload } = useAsyncData<Banner[]>({
        deps: [user?.id],
        enabled: enabled && isReady,
        resetOnLoad: true,
        fetcher: () => getBanners({ limit: ACTIVE_BANNERS_LIMIT, sort: "priority_desc" }),
        initialData: [],
    })

    return { banners, error, loading, reload }
}
