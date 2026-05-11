import { Alert } from "react-native"

import { translate } from "@/i18n/translations"
import { ApiError } from "@/services/api/client"

const ALERT_DEDUP_WINDOW_MS = 1200

let lastAlertMessage = ""
let lastAlertAt = 0

function getBackendUnavailableMessage() {
    return translate("auth.error.backendUnavailable")
}

function getInvalidCredentialsMessage() {
    return translate("auth.error.invalidCredentials")
}

function getAuthRequiredMessage() {
    return translate("auth.error.authRequired")
}

function getInvalidVerificationCodeMessage() {
    return translate("auth.error.invalidCode")
}

function normalizeMessage(message: string, fallback: string) {
    const trimmedMessage = message.trim()
    const loweredMessage = trimmedMessage.toLowerCase()

    if (!trimmedMessage) {
        return fallback
    }

    if (
        loweredMessage.includes("invalid credentials") ||
        loweredMessage.includes("invalid website credentials")
    ) {
        return getInvalidCredentialsMessage()
    }

    if (loweredMessage.includes("could not validate credentials")) {
        return getAuthRequiredMessage()
    }

    if (
        loweredMessage.includes("invalid verification code") ||
        loweredMessage.includes("invalid or expired verification code")
    ) {
        return getInvalidVerificationCodeMessage()
    }

    if (
        loweredMessage.includes("<!doctype html") ||
        loweredMessage.includes("<html") ||
        loweredMessage.includes("unexpected token '<'") ||
        loweredMessage.includes("failed to fetch") ||
        loweredMessage.includes("network request failed") ||
        loweredMessage.includes("request timed out") ||
        loweredMessage.includes("service is temporarily unavailable")
    ) {
        return getBackendUnavailableMessage()
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
        loweredMessage.includes("request timed out") ||
        loweredMessage.includes("unexpected token '<'") ||
        loweredMessage.includes("<!doctype html") ||
        loweredMessage.includes("<html")
    )
}

export function getErrorMessage(error: unknown, fallback?: string) {
    const resolvedFallback = fallback ?? translate("common.unknownError")

    if (error instanceof ApiError && error.status >= 500) {
        return getBackendUnavailableMessage()
    }

    if (error instanceof ApiError && [401, 403].includes(error.status)) {
        return normalizeMessage(error.message, getAuthRequiredMessage())
    }

    if (error instanceof Error && error.message) {
        return normalizeMessage(error.message, resolvedFallback)
    }

    return resolvedFallback
}

export function showBackendErrorAlert(error: unknown, fallback?: string) {
    if (!isBackendError(error)) {
        return
    }

    if (error instanceof ApiError && [401, 403].includes(error.status)) {
        return
    }

    const message = getErrorMessage(error, fallback ?? getBackendUnavailableMessage())
    const now = Date.now()

    if (message === lastAlertMessage && now - lastAlertAt < ALERT_DEDUP_WINDOW_MS) {
        return
    }

    lastAlertMessage = message
    lastAlertAt = now
    Alert.alert(translate("common.errorTitle"), message)
}
