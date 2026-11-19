import Constants from "expo-constants"

type AppExtraConfig = {
    apiBaseUrl?: unknown
    appIntegrity?: {
        androidCloudProjectNumber?: unknown
    }
}

const extra = Constants.expoConfig?.extra as AppExtraConfig | undefined

function optionalString(value: unknown) {
    return typeof value === "string" ? value.trim() : ""
}

const apiBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL?.trim() || optionalString(extra?.apiBaseUrl)
const androidCloudProjectNumber =
    process.env.EXPO_PUBLIC_PLAY_INTEGRITY_CLOUD_PROJECT_NUMBER?.trim() ||
    optionalString(extra?.appIntegrity?.androidCloudProjectNumber)

export const API_BASE_URL = apiBaseUrl
export const ANDROID_CLOUD_PROJECT_NUMBER = androidCloudProjectNumber || null
