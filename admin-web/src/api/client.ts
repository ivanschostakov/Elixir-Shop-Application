import type { AdminAuthResponse } from "./types"

const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api/v1/admin"
let accessToken: string | null = null
let authListener: ((auth: AdminAuthResponse | null) => void) | null = null
let refreshPromise: Promise<AdminAuthResponse> | null = null

export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(status: number, message: string, detail: unknown) {
    super(message)
    this.status = status
    this.detail = detail
  }
}

export function setAccessToken(token: string | null) {
  accessToken = token
}

export function setAuthListener(listener: ((auth: AdminAuthResponse | null) => void) | null) {
  authListener = listener
}

async function parseError(response: Response): Promise<ApiError> {
  let detail: unknown = null
  try {
    const body = (await response.json()) as { detail?: unknown }
    detail = body.detail
  } catch {
    detail = response.statusText
  }
  const message =
    typeof detail === "string"
      ? detail
      : typeof detail === "object" && detail && "message" in detail
        ? String((detail as { message: unknown }).message)
        : response.statusText || "Request failed"
  return new ApiError(response.status, message, detail)
}

export async function refreshAdminSession(): Promise<AdminAuthResponse> {
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      credentials: "include",
      headers: { Accept: "application/json" },
    })
      .then(async (response) => {
        if (!response.ok) throw await parseError(response)
        const auth = (await response.json()) as AdminAuthResponse
        setAccessToken(auth.access_token)
        authListener?.(auth)
        return auth
      })
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
  retryAuth = true,
): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set("Accept", "application/json")
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json")
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`)
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: "include",
  })
  if (response.status === 401 && retryAuth && !path.startsWith("/auth/")) {
    try {
      await refreshAdminSession()
      return apiRequest<T>(path, init, false)
    } catch {
      setAccessToken(null)
      authListener?.(null)
    }
  }
  if (!response.ok) throw await parseError(response)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export function queryString(values: Record<string, string | number | boolean | null | undefined>) {
  const params = new URLSearchParams()
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value))
  })
  const serialized = params.toString()
  return serialized ? `?${serialized}` : ""
}
