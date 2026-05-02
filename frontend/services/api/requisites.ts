import { ENDPOINTS } from "@/services/api/constants"
import { apiGet } from "@/services/api/client"
import type { RequisiteRead } from "@/types/requisite"

export function getRequisites(): Promise<RequisiteRead[]> {
    return apiGet<RequisiteRead[]>(
        ENDPOINTS.REQUISITES,
        undefined,
        { auth: false, retryOnUnauthorized: false },
    )
}
