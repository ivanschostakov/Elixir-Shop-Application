import { apiGet } from "@/services/api/client"
import { ENDPOINTS } from "@/services/api/constants"
import type { AppVersionPolicy } from "@/services/api/app-version.types"

export function getAppVersionPolicy(): Promise<AppVersionPolicy> {
    return apiGet<AppVersionPolicy>(ENDPOINTS.APP_VERSION, undefined, { auth: false })
}
