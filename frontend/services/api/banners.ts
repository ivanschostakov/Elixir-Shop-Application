import { ENDPOINTS } from "@/services/api/constants"
import { apiFetch, apiGet } from "@/services/api/client"
import type { Banner } from "@/types/banner"

export type BannerApiSort = "newest" | "priority_desc" | "priority_asc"

export type GetBannersOptions = {
    limit?: number
    offset?: number
    sort?: BannerApiSort
}

export function getBanners({
    limit = 10,
    offset,
    sort = "priority_desc",
}: GetBannersOptions = {}): Promise<Banner[]> {
    return apiGet<Banner[]>(ENDPOINTS.BANNERS, { limit, offset, sort })
}

export function recordBannerClick(bannerId: number, targetUrl?: string | null): Promise<void> {
    return apiFetch<void>(
        `${ENDPOINTS.BANNERS}/${bannerId}/click`,
        { method: "POST" },
        targetUrl ? { target_url: targetUrl } : undefined,
    )
}

export function recordBannerImpression(bannerId: number): Promise<void> {
    return apiFetch<void>(
        `${ENDPOINTS.BANNERS}/${bannerId}/impression`,
        { method: "POST" },
    )
}
