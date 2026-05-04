import Constants from "expo-constants"

type AppExtraConfig = {
    apiBaseUrl?: unknown
    appJsVersion?: unknown
    appIntegrity?: {
        androidCloudProjectNumber?: unknown
    }
}

const extra = Constants.expoConfig?.extra as AppExtraConfig | undefined

function optionalString(value: unknown) {
    return typeof value === "string" ? value.trim() : ""
}

function optionalNumberString(value: unknown) {
    if (typeof value === "number" && Number.isFinite(value)) {
        return String(value)
    }

    return optionalString(value)
}

function parseVersion(value: string) {
    const version = Number(value)
    return Number.isFinite(version) ? version : 1
}

const apiBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL?.trim() || optionalString(extra?.apiBaseUrl)
const appJsVersion = process.env.EXPO_PUBLIC_APP_JS_VERSION?.trim() || optionalNumberString(extra?.appJsVersion)
const androidCloudProjectNumber =
    process.env.EXPO_PUBLIC_PLAY_INTEGRITY_CLOUD_PROJECT_NUMBER?.trim() ||
    optionalString(extra?.appIntegrity?.androidCloudProjectNumber)

export const API_BASE_URL = apiBaseUrl
export const APP_JS_VERSION = appJsVersion ? parseVersion(appJsVersion) : 1
export const ANDROID_CLOUD_PROJECT_NUMBER = androidCloudProjectNumber || null
