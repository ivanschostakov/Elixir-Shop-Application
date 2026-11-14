import { useAsyncData } from "@/hooks/shared/use-async-data"
import { checkMyBenefits } from "@/services/api/benefits"
import type { BenefitCheckPayload, BenefitCheckResponse } from "@/services/api/benefits.types"

export function useOrderBenefits(
    scope: readonly unknown[],
    enabled: boolean,
    payload: BenefitCheckPayload,
) {
    return useAsyncData<BenefitCheckResponse | null>({
        deps: [...scope, payload],
        enabled,
        fetcher: () => checkMyBenefits(payload),
        initialData: null,
        preserveDataOnError: false,
    })
}
