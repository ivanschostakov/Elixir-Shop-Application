const apiBaseUrl =
    process.env.EXPO_PUBLIC_API_BASE_URL ??
    process.env.API_BASE_URL

if (!apiBaseUrl) {
    throw new Error("Missing EXPO_PUBLIC_API_BASE_URL in the Expo environment")
}

export const API_BASE_URL = apiBaseUrl
export const ENDPOINTS = {
    AUTH: "/v1/auth",
    DELIVERY: "/v1/delivery",
    PAYMENTS: "/v1/payments",
    PRODUCT_CATEGORIES: "/v1/product-categories",
    PRODUCTS: "/v1/products",
    USERS: "/v1/users",
}
