import { API_BASE_URL } from "@/services/api/constants"

const API_MEDIA_PATH_PREFIXES = [
    "/api/v1/community-media/",
    "/media/avatars/",
]

function getApiOrigin() {
    try {
        return new URL(API_BASE_URL).origin
    } catch {
        return ""
    }
}

/**
 * API media links are sometimes generated behind a reverse proxy and can carry
 * the container's host or http scheme. Keep the signed path/query intact while
 * using the same public origin as the API requests made by the app.
 */
export function resolveApiMediaUri(uri: string | null | undefined) {
    const trimmedUri = uri?.trim()
    if (!trimmedUri) return null

    const apiOrigin = getApiOrigin()
    if (!apiOrigin) return trimmedUri

    try {
        const mediaUrl = new URL(trimmedUri, apiOrigin)
        if (trimmedUri.startsWith("/") || API_MEDIA_PATH_PREFIXES.some((prefix) => mediaUrl.pathname.startsWith(prefix))) {
            const publicApiUrl = new URL(apiOrigin)
            mediaUrl.protocol = publicApiUrl.protocol
            mediaUrl.host = publicApiUrl.host
        }
        return mediaUrl.toString()
    } catch {
        return trimmedUri
    }
}
