const apiBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL

if (!apiBaseUrl) {
    throw new Error("Missing EXPO_PUBLIC_API_BASE_URL in the Expo environment")
}

export const API_BASE_URL = apiBaseUrl
