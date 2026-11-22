import { ENDPOINTS } from "@/services/api/constants"
import { ApiError, apiPost } from "@/services/api/client"
import { commerceAccountRevision } from "@/services/commerce-account"
import type { BenefitCheckPayload, BenefitCheckResponse } from "@/services/api/benefits.types"

function benefitsPath(path: string) {
    return `${ENDPOINTS.USERS}/me/benefits${path}`
}

export function checkMyBenefits(payload: BenefitCheckPayload) {
    return apiPost<BenefitCheckResponse, BenefitCheckPayload>(benefitsPath("/check"), payload)
}

export async function checkMyBenefitsWithRetry(payload: BenefitCheckPayload) {
    const revision = commerceAccountRevision()
    const delays = [250, 750]
    for (let attempt = 0; ; attempt++) {
        try {
            return await checkMyBenefits(payload)
        } catch (error) {
            if (!(error instanceof ApiError) || error.status !== 503 || attempt >= delays.length
                || commerceAccountRevision() !== revision) throw error
            await new Promise(resolve => setTimeout(resolve, delays[attempt]))
            if (commerceAccountRevision() !== revision) throw error
        }
    }
}
