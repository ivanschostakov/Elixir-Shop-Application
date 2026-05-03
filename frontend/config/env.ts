const apiBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL
const appJsVersion = process.env.EXPO_PUBLIC_APP_JS_VERSION?.trim()

if (!apiBaseUrl) {
    throw new Error("Missing EXPO_PUBLIC_API_BASE_URL in the Expo environment")
}

export const API_BASE_URL = apiBaseUrl
export const APP_JS_VERSION = appJsVersion && Number.isFinite(Number(appJsVersion)) ? Number(appJsVersion) : 1
