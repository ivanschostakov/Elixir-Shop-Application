import { API_BASE_URL } from "@/services/api/constants"
import type { QueryParams, RequestOptions } from "@/services/api/client.types"
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

function buildUrl(baseUrl: string, path: string, query?: QueryParams): string {
    const url = new URL(`${baseUrl}${path}`)

    if (query) {
        for (const [key, value] of Object.entries(query)) {
            if (value === undefined || value === null) continue
            url.searchParams.append(key, String(value))
        }
    }

    return url.toString()
}

function buildHeaders(init?: RequestInit, auth = true): Headers {
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

    return headers
}

async function buildApiError(response: Response): Promise<ApiError> {
    const raw = await response.text().catch(() => "")
    let body: unknown = raw
    let message = raw || `HTTP ${response.status}`

    if (raw) {
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

async function request<T>(
    baseUrl: string,
    path: string,
    init?: RequestInit,
    query?: QueryParams,
    options?: RequestOptions,
    hasRetried = false,
): Promise<T> {
    const auth = options?.auth ?? true
    const retryOnUnauthorized = options?.retryOnUnauthorized ?? auth
    const response = await fetch(buildUrl(baseUrl, path, query), {
        headers: buildHeaders(init, auth),
        ...init,
    })

    if (
        response.status === 401 &&
        auth &&
        retryOnUnauthorized &&
        !hasRetried &&
        getAuthTokens()?.refreshToken
    ) {
        const refreshedTokens = await refreshAuthTokens()

        if (refreshedTokens?.accessToken) {
            return request<T>(baseUrl, path, init, query, options, true)
        }
    }

    if (!response.ok) {
        throw await buildApiError(response)
    }

    if (response.status === 204) return undefined as T
    return response.json() as Promise<T>
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
