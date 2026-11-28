import { Alert, Linking } from "react-native"

import { translate } from "@/i18n/translations"
import { ApiError } from "@/services/api/client"
import { AppIntegrityUnavailableError } from "@/services/app-integrity"

const ALERT_DEDUP_WINDOW_MS = 1200

let lastAlertMessage = ""
let lastAlertAt = 0

function androidIntegrityMessage(error: unknown) {
    if (error instanceof ApiError) {
        const code = (error.body as { detail?: { code?: string } } | null)?.detail?.code
        switch (code) {
            case "android_app_unrecognized": return "auth.error.playUpdate"
            case "android_device_unverified": return "auth.error.playDevice"
            case "android_app_unevaluated": return "auth.error.playUnevaluated"
            case "android_signing_mismatch": return "auth.error.playSigning"
            case "android_verifier_unavailable": return "auth.error.playBusy"
            case "android_proof_invalid": return "auth.error.deviceVerificationUnavailable"
        }
    }
    if (error instanceof AppIntegrityUnavailableError && error.platform === "android") {
        switch (error.nativeCode) {
            case "ERR_APP_INTEGRITY_PLAY_STORE_NOT_FOUND":
            case "ERR_APP_INTEGRITY_PLAY_STORE_OUTDATED":
            case "ERR_APP_INTEGRITY_PLAY_SERVICES_NOT_FOUND":
            case "ERR_APP_INTEGRITY_PLAY_SERVICES_OUTDATED": return "auth.error.playUnevaluated"
            case "ERR_APP_INTEGRITY_GOOGLE_SERVER_UNAVAILABLE":
            case "ERR_APP_INTEGRITY_TOO_MANY_REQUESTS": return "auth.error.playBusy"
            case "ERR_APP_INTEGRITY_NETWORK_ERROR": return "network.connectionFailed"
        }
    }
    return null
}

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

    if (loweredMessage.includes("invalid credentials")) {
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

    const androidMessage = androidIntegrityMessage(error)
    if (androidMessage) return translate(androidMessage)
    if (error instanceof AppIntegrityUnavailableError) {
        return translate("auth.error.deviceVerificationUnavailable")
    }

    if (error instanceof ApiError && error.status === 0) return translate("network.connectionFailed")

    if (error instanceof ApiError && error.status >= 500) {
        return getBackendUnavailableMessage()
    }

    if (error instanceof ApiError && error.status === 422) {
        const detail = (error.body as { detail?: unknown } | null)?.detail
        if (Array.isArray(detail) && detail.some(issue => Array.isArray(issue?.loc) && issue.loc.includes("email"))) {
            return translate("auth.error.invalidEmail")
        }
        return translate("common.validationError")
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
    const androidMessage = androidIntegrityMessage(error)
    if (!androidMessage && !isBackendError(error)) {
        return
    }

    if (!androidMessage && error instanceof ApiError && [401, 403].includes(error.status)) {
        return
    }

    const message = getErrorMessage(error, fallback ?? getBackendUnavailableMessage())
    const now = Date.now()

    if (message === lastAlertMessage && now - lastAlertAt < ALERT_DEDUP_WINDOW_MS) {
        return
    }

    lastAlertMessage = message
    lastAlertAt = now
    if (androidMessage === "auth.error.playUpdate") {
        Alert.alert(translate("common.errorTitle"), message, [
            { text: translate("common.cancel"), style: "cancel" },
            { text: "Google Play", onPress: () => {
                void Linking.openURL("https://play.google.com/store/apps/details?id=com.elixirpeptide.elixirpeptide")
                    .catch(() => Alert.alert(translate("common.errorTitle"), message))
            } },
        ])
        return
    }
    Alert.alert(translate("common.errorTitle"), message)
}
