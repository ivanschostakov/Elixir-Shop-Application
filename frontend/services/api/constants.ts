import { API_BASE_URL as ENV_API_BASE_URL } from "@/config/env"

export const API_BASE_URL = ENV_API_BASE_URL

export const ENDPOINTS = {
    APP_VERSION: "/v1/app-version",
    AUTH: "/v1/auth",
    BANNERS: "/v1/banners",
    DELIVERY: "/v1/delivery",
    PAYMENTS: "/v1/payments",
    PRODUCT_CATEGORIES: "/v1/product-categories",
    PRODUCTS: "/v1/products",
    REQUISITES: "/v1/requisites",
    USERS: "/v1/users",
}
