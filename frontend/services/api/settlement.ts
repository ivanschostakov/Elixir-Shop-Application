import { apiGet } from "@/services/api/client"
import { ENDPOINTS } from "@/services/api/constants"

export type SettlementResponse = {
    source: "moysklad"
    status: "fresh" | "stale" | "unavailable" | "unlinked"
    balance_rubles: string | null
    total_purchases_rubles: string | null
    loyalty_program: 0 | 1 | 2 | null
    own_promo_code: string | null
    referrer_promo_code: string | null
    fetched_at: string | null
    issue: string | null
}

export function getMySettlement() {
    return apiGet<SettlementResponse>(`${ENDPOINTS.USERS}/me/referral-profile/settlement`)
}
