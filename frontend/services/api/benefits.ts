import { ENDPOINTS } from "@/services/api/constants"
import { apiPost } from "@/services/api/client"
import type { BenefitCheckPayload, BenefitCheckResponse } from "@/services/api/benefits.types"

function benefitsPath(path: string) {
    return `${ENDPOINTS.USERS}/me/benefits${path}`
}

export function checkMyBenefits(payload: BenefitCheckPayload) {
    return apiPost<BenefitCheckResponse, BenefitCheckPayload>(benefitsPath("/check"), payload)
}
