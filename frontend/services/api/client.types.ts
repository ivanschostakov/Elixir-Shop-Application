export type QueryValue = string | number | boolean | null | undefined
export type QueryParams = Record<string, QueryValue>

export type RequestOptions = {
    responseType?: "blob"
    auth?: boolean
    appIntegrityAction?: string
    retryOnUnauthorized?: boolean
    timeoutMs?: number
}
