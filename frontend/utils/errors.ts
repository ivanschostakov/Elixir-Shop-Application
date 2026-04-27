export function getErrorMessage(error: unknown, fallback = "Unknown error") {
    if (error instanceof Error && error.message) {
        return error.message
    }

    return fallback
}
