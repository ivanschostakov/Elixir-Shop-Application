import * as AppIntegrity from "@expo/app-integrity"
import * as SecureStore from "expo-secure-store"
import { Platform } from "react-native"
import { ANDROID_CLOUD_PROJECT_NUMBER, API_BASE_URL } from "@/config/env"
import { getAuthTokens, refreshAuthTokens } from "@/services/auth/session"
import { getTelegramInitData } from "@/services/telegram/telegram-web-app"
import { fetchTextWithDeadline, REQUEST_TIMEOUT_MS } from "@/services/api/request-deadline"

const IOS_APP_ATTEST_KEY_STORAGE_KEY = "elixirpeptide.appIntegrity.iosKeyId"
const IOS_APP_ATTEST_REGISTERED_STORAGE_KEY = "elixirpeptide.appIntegrity.iosRegisteredKeyId"
const IOS_APP_ATTEST_STATE_VERSION_STORAGE_KEY = "elixirpeptide.appIntegrity.iosStateVersion"
const IOS_APP_ATTEST_STATE_VERSION = "2"
const APP_INTEGRITY_HEADERS = {
    action: "X-App-Integrity-Action",
    keyId: "X-App-Integrity-Key-Id",
    platform: "X-App-Integrity-Platform",
    requestHash: "X-App-Integrity-Request-Hash",
    token: "X-App-Integrity-Token",
} as const

let preparedAndroidProjectNumber: string | null = null
let androidPreparation: Promise<void> | null = null
let androidNativeRetryAt = 0
let androidProjectNumberRequest: Promise<string> | null = null
let iosOperationQueue: Promise<unknown> = Promise.resolve()
function checkDeadline(signal: AbortSignal) {
    if (signal.aborted) throw new Error("integrity_timeout")
}

// App Attest shares one device key; concurrent recovery must not delete another request's key.
function withIosKeyLock<T>(operation: (signal: AbortSignal) => Promise<T>): Promise<T> {
    const controller = new AbortController()
    const timeout = new Promise<never>((_, reject) => {
        controller.signal.addEventListener("abort", () => reject(new Error("integrity_timeout")))
    })
    const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
    const result = iosOperationQueue.then(() => {
        checkDeadline(controller.signal)
        return Promise.race([operation(controller.signal), timeout])
    })
    iosOperationQueue = result.catch(() => undefined)
    return Promise.race([result, timeout]).finally(() => clearTimeout(timer))
}

async function retryIosService<T>(operation: () => Promise<T>, signal: AbortSignal): Promise<T> {
    for (let attempt = 0; ; attempt++) {
        try {
            checkDeadline(signal)
            const value = await operation()
            checkDeadline(signal)
            return value
        } catch (error) {
            checkDeadline(signal)
            const code = (error as { code?: string } | null)?.code
            const retryable = code === "ERR_APP_INTEGRITY_SERVER_UNAVAILABLE" || code === "ERR_APP_INTEGRITY_SYSTEM_FAILURE"
            if (!retryable || attempt >= 2) throw error
            await new Promise(resolve => setTimeout(resolve, 400 * 2 ** attempt))
        }
    }
}

export class AppIntegrityUnavailableError extends Error {
    action: string
    platform: string
    reason: string
    nativeCode?: string

    constructor(action: string, platform: string, reason: string, nativeCode?: string) {
        super(`App integrity check unavailable: ${reason}`)
        this.name = "AppIntegrityUnavailableError"
        this.action = action
        this.platform = platform
        this.reason = reason
        this.nativeCode = nativeCode
    }
}

class AppIntegrityApiError extends Error {
    status: number

    constructor(status: number, message: string) {
        super(message)
        this.name = "AppIntegrityApiError"
        this.status = status
    }
}

type AppIntegrityHeaders = Record<string, string>

type IosChallengeResponse = {
    challenge: string
}

type IosRegisterResponse = {
    key_id: string
    environment: string
}

type AppIntegrityConfigResponse = {
    android_cloud_project_number?: unknown
}

async function getAndroidCloudProjectNumber() {
    if (!androidProjectNumberRequest) {
        androidProjectNumberRequest = appIntegrityFetch<AppIntegrityConfigResponse>("/v1/app-integrity/config", {
            method: "GET",
        })
            .then(({ android_cloud_project_number: projectNumber }) => {
                if (typeof projectNumber !== "string" || !projectNumber.trim()) {
                    if (ANDROID_CLOUD_PROJECT_NUMBER) {
                        return ANDROID_CLOUD_PROJECT_NUMBER
                    }
                    throw new Error("missing_android_cloud_project_number")
                }
                return projectNumber.trim()
            })
            .catch((error) => {
                androidProjectNumberRequest = null
                if (ANDROID_CLOUD_PROJECT_NUMBER) {
                    return ANDROID_CLOUD_PROJECT_NUMBER
                }
                throw error
            })
    }

    return androidProjectNumberRequest
}

function randomHex(bytesLength: number) {
    const bytes = new Uint8Array(bytesLength)
    const cryptoObject = globalThis.crypto
    if (cryptoObject?.getRandomValues) {
        cryptoObject.getRandomValues(bytes)
    } else {
        for (let index = 0; index < bytes.length; index += 1) {
            bytes[index] = Math.floor(Math.random() * 256)
        }
    }

    return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("")
}

function buildRequestHash(action: string) {
    return `${action}:${Date.now()}:${randomHex(16)}`
}

function describeIntegrityError(error: unknown) {
    if (error instanceof AppIntegrityApiError) {
        return `api_${error.status}: ${error.message}`
    }

    if (error instanceof Error) {
        return `${error.name}: ${error.message}`
    }

    return String(error)
}

function createUnavailableError(action: string, platform: string, error: unknown) {
    const reason = typeof error === "string" ? error : describeIntegrityError(error)
    if (__DEV__) {
        console.warn("[app-integrity] failed", { action, platform, reason, error })
    }
    const code = (error as { code?: unknown } | null)?.code
    return new AppIntegrityUnavailableError(action, platform, reason, typeof code === "string" ? code : undefined)
}

async function appIntegrityFetch<T>(path: string, init: RequestInit, hasRetried = false): Promise<T> {
    if (!API_BASE_URL) {
        throw new Error("missing_api_base_url")
    }

    const headers = new Headers(init.headers)
    const tokens = getAuthTokens()

    headers.set("Accept", "application/json")
    if (init.body !== undefined) {
        headers.set("Content-Type", "application/json")
    }
    if (tokens?.accessToken) {
        headers.set("Authorization", `Bearer ${tokens.accessToken}`)
    }

    const { response, text } = await fetchTextWithDeadline(`${API_BASE_URL}${path}`, { ...init, headers })

    if (response.status === 401 && !hasRetried && getAuthTokens()?.refreshToken) {
        const refreshedTokens = await refreshAuthTokens()
        if (refreshedTokens?.accessToken) {
            return appIntegrityFetch<T>(path, init, true)
        }
    }

    if (!response.ok) {
        throw new AppIntegrityApiError(response.status, text || `HTTP ${response.status}`)
    }

    return JSON.parse(text) as T
}

async function fetchIosChallenge(purpose: "attestation" | "assertion", action?: string) {
    return appIntegrityFetch<IosChallengeResponse>("/v1/app-integrity/ios/challenge", {
        method: "POST",
        body: JSON.stringify({
            purpose,
            ...(action ? { action } : {}),
        }),
    })
}

async function registerIosKey(keyId: string, challenge: string, attestationObject: string) {
    return appIntegrityFetch<IosRegisterResponse>("/v1/app-integrity/ios/register", {
        method: "POST",
        body: JSON.stringify({
            key_id: keyId,
            challenge,
            attestation_object: attestationObject,
        }),
    })
}

async function ensureAndroidProvider(cloudProjectNumber: string) {
    if (preparedAndroidProjectNumber === cloudProjectNumber) {
        return
    }

    if (!androidPreparation) {
        androidPreparation = AppIntegrity.prepareIntegrityTokenProviderAsync(cloudProjectNumber)
            .then(() => { preparedAndroidProjectNumber = cloudProjectNumber })
            .finally(() => { androidPreparation = null })
    }
    await androidPreparation
}

async function getAndroidIntegrityHeaders(action: string, requestHash: string): Promise<AppIntegrityHeaders> {
    const cloudProjectNumber = await getAndroidCloudProjectNumber()

    await ensureAndroidProvider(cloudProjectNumber)
    try {
        const token = await AppIntegrity.requestIntegrityCheckAsync(requestHash)
        return {
            [APP_INTEGRITY_HEADERS.action]: action,
            [APP_INTEGRITY_HEADERS.platform]: "android",
            [APP_INTEGRITY_HEADERS.requestHash]: requestHash,
            [APP_INTEGRITY_HEADERS.token]: token,
        }
    } catch (error) {
        if ((error as { code?: string } | null)?.code === "ERR_APP_INTEGRITY_PROVIDER_INVALID"
            || (error instanceof Error && error.message.includes("ERR_APP_INTEGRITY_PROVIDER_INVALID"))) {
            preparedAndroidProjectNumber = null
            await ensureAndroidProvider(cloudProjectNumber)
            const token = await AppIntegrity.requestIntegrityCheckAsync(requestHash)
            return {
                [APP_INTEGRITY_HEADERS.action]: action,
                [APP_INTEGRITY_HEADERS.platform]: "android",
                [APP_INTEGRITY_HEADERS.requestHash]: requestHash,
                [APP_INTEGRITY_HEADERS.token]: token,
            }
        }
        throw error
    }
}

async function getIosKeyId(signal: AbortSignal) {
    const storedKeyId = await SecureStore.getItemAsync(IOS_APP_ATTEST_KEY_STORAGE_KEY)
    checkDeadline(signal)
    if (storedKeyId) {
        return storedKeyId
    }

    const keyId = await AppIntegrity.generateKeyAsync()
    checkDeadline(signal)
    await SecureStore.setItemAsync(IOS_APP_ATTEST_KEY_STORAGE_KEY, keyId)
    return keyId
}

async function clearIosKeyState() {
    await Promise.all([
        SecureStore.deleteItemAsync(IOS_APP_ATTEST_KEY_STORAGE_KEY),
        SecureStore.deleteItemAsync(IOS_APP_ATTEST_REGISTERED_STORAGE_KEY),
    ])
}

export async function resetAppIntegrityState() {
    preparedAndroidProjectNumber = null

    if (Platform.OS === "ios") {
        await withIosKeyLock(async () => {
            await clearIosKeyState()
        })
    }
}

async function migrateIosKeyStateIfNeeded(signal: AbortSignal) {
    const stateVersion = await SecureStore.getItemAsync(IOS_APP_ATTEST_STATE_VERSION_STORAGE_KEY)
    checkDeadline(signal)
    if (stateVersion === IOS_APP_ATTEST_STATE_VERSION) {
        return
    }

    await clearIosKeyState()
    await SecureStore.setItemAsync(IOS_APP_ATTEST_STATE_VERSION_STORAGE_KEY, IOS_APP_ATTEST_STATE_VERSION)
}

async function ensureIosKeyStateMigrated(signal: AbortSignal) {
    return migrateIosKeyStateIfNeeded(signal)
}

function isRecoverableIosKeyError(error: unknown) {
    if (error instanceof AppIntegrityApiError && [403, 409].includes(error.status)) {
        return true
    }

    const errorText = error instanceof Error ? `${error.name} ${error.message}` : String(error)
    const normalizedErrorText = errorText.toLowerCase()
    return (
        errorText.includes("ERR_APP_INTEGRITY_INVALID_INPUT") ||
        errorText.includes("ERR_APP_INTEGRITY_INVALID_KEY") ||
        normalizedErrorText.includes("invalid input") ||
        normalizedErrorText.includes("invalid key") ||
        normalizedErrorText.includes("already registered")
    )
}

async function registerIosKeyIfNeeded(signal: AbortSignal) {
    const keyId = await getIosKeyId(signal)
    const registeredKeyId = await SecureStore.getItemAsync(IOS_APP_ATTEST_REGISTERED_STORAGE_KEY)
    if (registeredKeyId === keyId) {
        return keyId
    }

    const { challenge } = await fetchIosChallenge("attestation")
    const attestationObject = await retryIosService(() => AppIntegrity.attestKeyAsync(keyId, challenge), signal)
    checkDeadline(signal)
    await registerIosKey(keyId, challenge, attestationObject)
    checkDeadline(signal)
    await SecureStore.setItemAsync(IOS_APP_ATTEST_REGISTERED_STORAGE_KEY, keyId)
    return keyId
}

async function ensureIosKeyRegistered(signal: AbortSignal) {
    return registerIosKeyIfNeeded(signal)
}

async function getIosIntegrityHeaders(action: string, signal: AbortSignal): Promise<AppIntegrityHeaders> {
    if (!AppIntegrity.isSupported) {
        throw new Error("ios_app_attest_unsupported")
    }

    await ensureIosKeyStateMigrated(signal)

    for (let attempt = 0; attempt < 2; attempt += 1) {
        try {
            const keyId = await ensureIosKeyRegistered(signal)
            const { challenge } = await fetchIosChallenge("assertion", action)
            const token = await retryIosService(() => AppIntegrity.generateAssertionAsync(keyId, challenge), signal)
            // Keep the key queue until the server acknowledges the counter, not
            // until a potentially long upload or AI response has completed.
            const { grant } = await appIntegrityFetch<{ grant: string }>("/v1/app-integrity/ios/verify", {
                method: "POST",
                body: JSON.stringify({ key_id: keyId, challenge, assertion: token, action }),
            })
            checkDeadline(signal)
            if (typeof grant !== "string" || !grant) throw new Error("invalid_ios_assertion_grant")
            return {
                [APP_INTEGRITY_HEADERS.action]: action,
                [APP_INTEGRITY_HEADERS.keyId]: keyId,
                [APP_INTEGRITY_HEADERS.platform]: "ios",
                [APP_INTEGRITY_HEADERS.requestHash]: grant,
                [APP_INTEGRITY_HEADERS.token]: `ios-grant:${grant}`,
            }
        } catch (error) {
            checkDeadline(signal)
            if (attempt === 0 && isRecoverableIosKeyError(error)) {
                await clearIosKeyState()
                continue
            }
            throw error
        }
    }
    throw new Error("ios_app_attest_unavailable")
}

export async function getAppIntegrityHeaders(action?: string): Promise<AppIntegrityHeaders> {
    if (!action) {
        return {}
    }

    if (Platform.OS === "web") {
        const initData = getTelegramInitData()
        if (!initData) {
            return {}
        }

        return {
            [APP_INTEGRITY_HEADERS.action]: action,
            [APP_INTEGRITY_HEADERS.platform]: "telegram",
            [APP_INTEGRITY_HEADERS.requestHash]: buildRequestHash(action),
            [APP_INTEGRITY_HEADERS.token]: initData,
        }
    }

    try {
        if (Platform.OS === "android") {
            if (Date.now() < androidNativeRetryAt) {
                throw Object.assign(new Error("Play Integrity cooldown"), { code: "ERR_APP_INTEGRITY_TOO_MANY_REQUESTS" })
            }
            const requestHash = buildRequestHash(action)
            try {
                return await getAndroidIntegrityHeaders(action, requestHash)
            } catch (error) {
                const code = (error as { code?: string } | null)?.code
                if (code === "ERR_APP_INTEGRITY_TOO_MANY_REQUESTS" || code === "ERR_APP_INTEGRITY_GOOGLE_SERVER_UNAVAILABLE") {
                    androidNativeRetryAt = Date.now() + (code === "ERR_APP_INTEGRITY_TOO_MANY_REQUESTS" ? 60_000 : 5000)
                }
                throw error
            }
        }
        if (Platform.OS === "ios") {
            return await withIosKeyLock(signal => getIosIntegrityHeaders(action, signal))
        }
    } catch (error) {
        throw createUnavailableError(action, Platform.OS, error)
    }

    throw new AppIntegrityUnavailableError(action, Platform.OS, "unsupported_platform")
}
