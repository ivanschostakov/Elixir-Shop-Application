import { Alert } from "react-native"

import { ApiError } from "@/services/api/client"

const BACKEND_UNAVAILABLE_MESSAGE = "Сервер временно недоступен. Попробуйте еще раз чуть позже."
const INVALID_CREDENTIALS_MESSAGE = "Неверный логин или пароль."
const AUTH_REQUIRED_MESSAGE = "Требуется вход в аккаунт."
const INVALID_VERIFICATION_CODE_MESSAGE = "Неверный или просроченный код подтверждения."
const ALERT_TITLE = "Ошибка"
const ALERT_DEDUP_WINDOW_MS = 1200

let lastAlertMessage = ""
let lastAlertAt = 0

function normalizeMessage(message: string, fallback: string) {
    const trimmedMessage = message.trim()
    const loweredMessage = trimmedMessage.toLowerCase()

    if (!trimmedMessage) {
        return fallback
    }

    if (loweredMessage.includes("invalid credentials")) {
        return INVALID_CREDENTIALS_MESSAGE
    }

    if (loweredMessage.includes("could not validate credentials")) {
        return AUTH_REQUIRED_MESSAGE
    }

    if (
        loweredMessage.includes("invalid verification code") ||
        loweredMessage.includes("invalid or expired verification code")
    ) {
        return INVALID_VERIFICATION_CODE_MESSAGE
    }

    if (
        loweredMessage.includes("<!doctype html") ||
        loweredMessage.includes("<html") ||
        loweredMessage.includes("unexpected token '<'") ||
        loweredMessage.includes("failed to fetch") ||
        loweredMessage.includes("network request failed") ||
        loweredMessage.includes("service is temporarily unavailable")
    ) {
        return BACKEND_UNAVAILABLE_MESSAGE
    }

    return trimmedMessage
}

export function isBackendError(error: unknown) {
    if (error instanceof ApiError) {
        return true
    }

    if (!(error instanceof Error)) {
        return false
    }

    const loweredMessage = error.message.toLowerCase()
    return (
        loweredMessage.includes("failed to fetch") ||
        loweredMessage.includes("network request failed") ||
        loweredMessage.includes("unexpected token '<'") ||
        loweredMessage.includes("<!doctype html") ||
        loweredMessage.includes("<html")
    )
}

export function getErrorMessage(error: unknown, fallback = "Unknown error") {
    if (error instanceof ApiError && [401, 403].includes(error.status)) {
        return AUTH_REQUIRED_MESSAGE
    }

    if (error instanceof ApiError && error.status >= 500) {
        return BACKEND_UNAVAILABLE_MESSAGE
    }

    if (error instanceof Error && error.message) {
        return normalizeMessage(error.message, fallback)
    }

    return fallback
}

export function showBackendErrorAlert(error: unknown, fallback = BACKEND_UNAVAILABLE_MESSAGE) {
    if (!isBackendError(error)) {
        return
    }

    if (error instanceof ApiError && [401, 403].includes(error.status)) {
        return
    }

    const message = getErrorMessage(error, fallback)
    const now = Date.now()

    if (message === lastAlertMessage && now - lastAlertAt < ALERT_DEDUP_WINDOW_MS) {
        return
    }

    lastAlertMessage = message
    lastAlertAt = now
    Alert.alert(ALERT_TITLE, message)
}
