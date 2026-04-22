import { ApiError } from "@/services/api/client"

export function getErrorMessage(error: unknown, fallback: string) {
    if (error instanceof ApiError && error.message) {
        return error.message
    }

    if (error instanceof Error && error.message) {
        return error.message
    }

    return fallback
}
