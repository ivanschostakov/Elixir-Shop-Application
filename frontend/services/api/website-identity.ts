import { ApiError, apiGet, apiPost } from "@/services/api/client"
import { ENDPOINTS } from "@/services/api/constants"
import type { WebsiteIdentity, WebsiteIdentityLoginPayload } from "@/services/api/website-identity.types"

function websiteIdentityPath(path = "") {
    return `${ENDPOINTS.USERS}/me/website-identity${path}`
}

export async function getMyWebsiteIdentity(): Promise<WebsiteIdentity | null> {
    try {
        return await apiGet<WebsiteIdentity>(websiteIdentityPath())
    } catch (error) {
        if (error instanceof ApiError && error.status === 404) {
            return null
        }
        throw error
    }
}

export function linkMyWebsiteIdentity(payload: WebsiteIdentityLoginPayload): Promise<WebsiteIdentity> {
    return apiPost<WebsiteIdentity, WebsiteIdentityLoginPayload>(websiteIdentityPath("/link"), payload)
}
