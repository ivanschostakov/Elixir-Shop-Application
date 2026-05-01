import { API_BASE_URL as ENV_API_BASE_URL } from "@/config/env"

export const API_BASE_URL = ENV_API_BASE_URL

export const ENDPOINTS = {
    AUTH: "/v1/auth",
    DELIVERY: "/v1/delivery",
    PAYMENTS: "/v1/payments",
    PRODUCT_CATEGORIES: "/v1/product-categories",
    PRODUCTS: "/v1/products",
    USERS: "/v1/users",
}
