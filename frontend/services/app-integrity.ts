import * as AppIntegrity from "@expo/app-integrity"
import * as SecureStore from "expo-secure-store"
import { Platform } from "react-native"
import { ANDROID_CLOUD_PROJECT_NUMBER, API_BASE_URL, APP_INTEGRITY_DEV_TOKEN } from "@/config/env"
import { getAuthTokens, refreshAuthTokens } from "@/services/auth/session"
import { getTelegramInitData } from "@/services/telegram/telegram-web-app"

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
let androidProjectNumberRequest: Promise<string> | null = null
let iosRegistrationRequest: Promise<string> | null = null
let iosKeyStateMigrationRequest: Promise<void> | null = null

export class AppIntegrityUnavailableError extends Error {
    action: string
    platform: string
    reason: string

    constructor(action: string, platform: string, reason: string) {
        super(`App integrity check unavailable: ${reason}`)
        this.name = "AppIntegrityUnavailableError"
        this.action = action
        this.platform = platform
        this.reason = reason
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

function getDevTokenIntegrityHeaders(action: string): AppIntegrityHeaders | null {
    if (!__DEV__ || !APP_INTEGRITY_DEV_TOKEN) {
        return null
    }

    return {
        [APP_INTEGRITY_HEADERS.action]: action,
        [APP_INTEGRITY_HEADERS.platform]: Platform.OS === "android" ? "android" : "ios",
        [APP_INTEGRITY_HEADERS.requestHash]: buildRequestHash(action),
        [APP_INTEGRITY_HEADERS.token]: APP_INTEGRITY_DEV_TOKEN,
    }
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
    return new AppIntegrityUnavailableError(action, platform, reason)
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

    const response = await fetch(`${API_BASE_URL}${path}`, {
        ...init,
        headers,
    })

    if (response.status === 401 && !hasRetried && getAuthTokens()?.refreshToken) {
        const refreshedTokens = await refreshAuthTokens()
        if (refreshedTokens?.accessToken) {
            return appIntegrityFetch<T>(path, init, true)
        }
    }

    if (!response.ok) {
        const message = await response.text().catch(() => "")
        throw new AppIntegrityApiError(response.status, message || `HTTP ${response.status}`)
    }

    return response.json() as Promise<T>
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

    await AppIntegrity.prepareIntegrityTokenProviderAsync(cloudProjectNumber)
    preparedAndroidProjectNumber = cloudProjectNumber
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
        if (error instanceof Error && error.message.includes("ERR_APP_INTEGRITY_PROVIDER_INVALID")) {
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

async function getIosKeyId() {
    const storedKeyId = await SecureStore.getItemAsync(IOS_APP_ATTEST_KEY_STORAGE_KEY)
    if (storedKeyId) {
        return storedKeyId
    }

    const keyId = await AppIntegrity.generateKeyAsync()
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
        iosRegistrationRequest = null
        iosKeyStateMigrationRequest = null
        await clearIosKeyState()
    }
}

async function migrateIosKeyStateIfNeeded() {
    const stateVersion = await SecureStore.getItemAsync(IOS_APP_ATTEST_STATE_VERSION_STORAGE_KEY)
    if (stateVersion === IOS_APP_ATTEST_STATE_VERSION) {
        return
    }

    await clearIosKeyState()
    await SecureStore.setItemAsync(IOS_APP_ATTEST_STATE_VERSION_STORAGE_KEY, IOS_APP_ATTEST_STATE_VERSION)
}

async function ensureIosKeyStateMigrated() {
    if (!iosKeyStateMigrationRequest) {
        iosKeyStateMigrationRequest = migrateIosKeyStateIfNeeded().finally(() => {
            iosKeyStateMigrationRequest = null
        })
    }

    return iosKeyStateMigrationRequest
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

async function registerIosKeyIfNeeded() {
    const keyId = await getIosKeyId()
    const registeredKeyId = await SecureStore.getItemAsync(IOS_APP_ATTEST_REGISTERED_STORAGE_KEY)
    if (registeredKeyId === keyId) {
        return keyId
    }

    const { challenge } = await fetchIosChallenge("attestation")
    const attestationObject = await AppIntegrity.attestKeyAsync(keyId, challenge)
    await registerIosKey(keyId, challenge, attestationObject)
    await SecureStore.setItemAsync(IOS_APP_ATTEST_REGISTERED_STORAGE_KEY, keyId)
    return keyId
}

async function ensureIosKeyRegistered() {
    if (!iosRegistrationRequest) {
        iosRegistrationRequest = registerIosKeyIfNeeded().finally(() => {
            iosRegistrationRequest = null
        })
    }

    return iosRegistrationRequest
}

async function getIosIntegrityHeaders(action: string): Promise<AppIntegrityHeaders> {
    if (!AppIntegrity.isSupported) {
        throw new Error("ios_app_attest_unsupported")
    }

    await ensureIosKeyStateMigrated()

    for (let attempt = 0; attempt < 2; attempt += 1) {
        try {
            const keyId = await ensureIosKeyRegistered()
            const { challenge } = await fetchIosChallenge("assertion", action)
            const token = await AppIntegrity.generateAssertionAsync(keyId, challenge)
            return {
                [APP_INTEGRITY_HEADERS.action]: action,
                [APP_INTEGRITY_HEADERS.keyId]: keyId,
                [APP_INTEGRITY_HEADERS.platform]: "ios",
                [APP_INTEGRITY_HEADERS.requestHash]: challenge,
                [APP_INTEGRITY_HEADERS.token]: token,
            }
        } catch (error) {
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

    const devTokenHeaders = getDevTokenIntegrityHeaders(action)
    if (devTokenHeaders) {
        return devTokenHeaders
    }

    try {
        if (Platform.OS === "android") {
            const requestHash = buildRequestHash(action)
            return await getAndroidIntegrityHeaders(action, requestHash)
        }
        if (Platform.OS === "ios") {
            return await getIosIntegrityHeaders(action)
        }
    } catch (error) {
        throw createUnavailableError(action, Platform.OS, error)
    }

    throw new AppIntegrityUnavailableError(action, Platform.OS, "unsupported_platform")
}
