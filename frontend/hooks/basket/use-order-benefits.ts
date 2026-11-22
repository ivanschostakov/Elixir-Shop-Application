import { useAsyncData } from "@/hooks/shared/use-async-data"
import { checkMyBenefitsWithRetry } from "@/services/api/benefits"
import type { BenefitCheckPayload, BenefitCheckResponse } from "@/services/api/benefits.types"

export function useOrderBenefits(
    scope: readonly unknown[],
    enabled: boolean,
    payload: BenefitCheckPayload,
) {
    return useAsyncData<BenefitCheckResponse | null>({
        deps: [...scope, payload],
        enabled,
        fetcher: () => checkMyBenefitsWithRetry(payload),
        initialData: null,
        preserveDataOnError: false,
        showErrorAlert: false,
    })
}
