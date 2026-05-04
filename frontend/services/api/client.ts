import { API_BASE_URL } from "@/services/api/constants"
import type { QueryParams, RequestOptions } from "@/services/api/client.types"
import { getAppIntegrityHeaders, resetAppIntegrityState } from "@/services/app-integrity"
import { getAuthTokens, refreshAuthTokens } from "@/services/auth/session"

export class ApiError extends Error {
    status: number
    body: unknown

    constructor(status: number, message: string, body: unknown = null) {
        super(message)
        this.name = "ApiError"
        this.status = status
        this.body = body
    }
}

const SERVICE_UNAVAILABLE_MESSAGE = "Service is temporarily unavailable. Please try again later."
const INVALID_RESPONSE_MESSAGE = "Unexpected response from server."

function isLikelyHtmlResponse(payload: string) {
    const trimmedPayload = payload.trim().toLowerCase()

    return trimmedPayload.startsWith("<!doctype html") || trimmedPayload.startsWith("<html")
}

function buildUrl(baseUrl: string, path: string, query?: QueryParams): string {
    const normalizedBaseUrl = baseUrl.trim()
    if (!normalizedBaseUrl) {
        throw new ApiError(503, SERVICE_UNAVAILABLE_MESSAGE, "Missing API base URL")
    }

    let url: URL
    try {
        url = new URL(`${normalizedBaseUrl}${path}`)
    } catch {
        throw new ApiError(503, SERVICE_UNAVAILABLE_MESSAGE, "Invalid API base URL")
    }

    if (query) {
        for (const [key, value] of Object.entries(query)) {
            if (value === undefined || value === null) continue
            url.searchParams.append(key, String(value))
        }
    }

    return url.toString()
}

async function buildHeaders(init?: RequestInit, auth = true, options?: RequestOptions): Promise<Headers> {
    const headers = new Headers(init?.headers ?? {})
    const tokens = getAuthTokens()
    const isFormDataBody =
        typeof FormData !== "undefined" &&
        init?.body instanceof FormData

    if (init?.body !== undefined && !isFormDataBody && !headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json")
    }

    if (auth && tokens?.accessToken) {
        headers.set("Authorization", `Bearer ${tokens.accessToken}`)
    }

    const appIntegrityHeaders = await getAppIntegrityHeaders(options?.appIntegrityAction)
    for (const [key, value] of Object.entries(appIntegrityHeaders)) {
        headers.set(key, value)
    }

    return headers
}

async function buildApiError(response: Response): Promise<ApiError> {
    const raw = await response.text().catch(() => "")
    let body: unknown = raw
    let message = raw || `HTTP ${response.status}`

    if (raw) {
        if (isLikelyHtmlResponse(raw)) {
            return new ApiError(response.status, SERVICE_UNAVAILABLE_MESSAGE, raw)
        }

        try {
            body = JSON.parse(raw)

            if (
                typeof body === "object" &&
                body !== null &&
                "detail" in body
            ) {
                if (typeof body.detail === "string") {
                    message = body.detail
                } else if (
                    typeof body.detail === "object" &&
                    body.detail !== null &&
                    "message" in body.detail &&
                    typeof body.detail.message === "string"
                ) {
                    message = body.detail.message
                }
            }
        } catch {
            body = raw
        }
    }

    return new ApiError(response.status, message, body)
}

function isAppIntegrityApiError(error: ApiError) {
    if (error.message === "App integrity check failed") {
        return true
    }

    return (
        typeof error.body === "object" &&
        error.body !== null &&
        "detail" in error.body &&
        error.body.detail === "App integrity check failed"
    )
}

async function request<T>(
    baseUrl: string,
    path: string,
    init?: RequestInit,
    query?: QueryParams,
    options?: RequestOptions,
    hasRetried = false,
    hasRetriedAppIntegrity = false,
): Promise<T> {
    const auth = options?.auth ?? true
    const retryOnUnauthorized = options?.retryOnUnauthorized ?? auth
    let response: Response

    try {
        response = await fetch(buildUrl(baseUrl, path, query), {
            ...init,
            headers: await buildHeaders(init, auth, options),
        })
    } catch {
        throw new ApiError(503, SERVICE_UNAVAILABLE_MESSAGE)
    }

    if (
        response.status === 401 &&
        auth &&
        retryOnUnauthorized &&
        !hasRetried &&
        getAuthTokens()?.refreshToken
    ) {
        const refreshedTokens = await refreshAuthTokens()

        if (refreshedTokens?.accessToken) {
            return request<T>(baseUrl, path, init, query, options, true, hasRetriedAppIntegrity)
        }
    }

    if (!response.ok) {
        const apiError = await buildApiError(response)

        if (
            response.status === 403 &&
            options?.appIntegrityAction &&
            !hasRetriedAppIntegrity &&
            isAppIntegrityApiError(apiError)
        ) {
            await resetAppIntegrityState()
            return request<T>(baseUrl, path, init, query, options, hasRetried, true)
        }

        throw apiError
    }

    if (response.status === 204) return undefined as T

    const rawResponse = await response.text()

    if (!rawResponse) {
        return undefined as T
    }

    try {
        return JSON.parse(rawResponse) as T
    } catch {
        if (isLikelyHtmlResponse(rawResponse)) {
            throw new ApiError(response.status, SERVICE_UNAVAILABLE_MESSAGE, rawResponse)
        }

        throw new ApiError(response.status, INVALID_RESPONSE_MESSAGE, rawResponse)
    }
}

export function apiFetch<T>(
    path: string,
    init?: RequestInit,
    query?: QueryParams,
    options?: RequestOptions,
): Promise<T> {
    return request<T>(API_BASE_URL, path, init, query, options)
}


export function apiGet<T>(path: string, query?: QueryParams, options?: RequestOptions): Promise<T> {
    return apiFetch<T>(path, { method: "GET" }, query, options)
}

export function apiPost<TResponse, TBody>(
    path: string,
    body: TBody,
    options?: RequestOptions,
): Promise<TResponse> {
    return apiFetch<TResponse>(path, { method: "POST", body: JSON.stringify(body) }, undefined, options)
}

export function apiPostMultipart<TResponse>(
    path: string,
    body: FormData,
    options?: RequestOptions,
): Promise<TResponse> {
    return apiFetch<TResponse>(path, { method: "POST", body }, undefined, options)
}

export function apiPatch<TResponse, TBody>(
    path: string,
    body: TBody,
    options?: RequestOptions,
): Promise<TResponse> {
    return apiFetch<TResponse>(path, { method: "PATCH", body: JSON.stringify(body) }, undefined, options)
}

export function apiDelete<TResponse = void>(path: string, options?: RequestOptions): Promise<TResponse> {
    return apiFetch<TResponse>(path, { method: "DELETE" }, undefined, options)
}
