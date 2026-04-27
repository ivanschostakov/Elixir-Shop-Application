import { translate, type TranslationKey } from "@/i18n/translations"
import { Href } from "expo-router"

export const ROUTES = {
    home: "/",
    discover: "/discover",
    basket: "/basket",
    checkout: "/checkout",
    delivery: "/delivery",
    favorites: "/favorites",
    register: "/register",
    login: "/login",
    payment: "/payment",
    profile: "/profile",
    profileHistory: "/profile-history",
    websiteAccount: "/website-account",
} as const

const PRODUCT_ROUTE_PREFIX = "/products/"

const headerTitleKeys: Record<string, TranslationKey> = {
    [ROUTES.home]: "app.name",
    [ROUTES.discover]: "route.discover",
    [ROUTES.basket]: "route.basket",
    [ROUTES.checkout]: "route.checkout",
    [ROUTES.delivery]: "route.delivery",
    [ROUTES.favorites]: "route.favorites",
    [ROUTES.payment]: "route.payment",
    [ROUTES.profile]: "route.profile",
    [ROUTES.profileHistory]: "route.profileHistory",
    [ROUTES.websiteAccount]: "route.websiteAccount",
}

export const PRIMARY_APP_ROUTES = [
    ROUTES.home,
    ROUTES.discover,
    ROUTES.favorites,
    ROUTES.basket,
    ROUTES.profile,
] as const

const FULLSCREEN_ROUTES = [
    ROUTES.delivery,
] as const

export function getProductRoute(productId: number | string): Href {
    return `${PRODUCT_ROUTE_PREFIX}${productId}`
}

export function isProductRoute(pathname: string) {
    return pathname.startsWith(PRODUCT_ROUTE_PREFIX)
}

export function getProductIdFromRoute(pathname: string) {
    if (!isProductRoute(pathname)) {
        return null
    }

    const productId = pathname.slice(PRODUCT_ROUTE_PREFIX.length).split("/")[0]
    return productId ? productId : null
}

export function isAuthRoute(pathname: string) {
    return pathname.startsWith("/login") || pathname === ROUTES.register
}

export function isPrimaryAppRoute(pathname: string) {
    return PRIMARY_APP_ROUTES.includes(pathname as (typeof PRIMARY_APP_ROUTES)[number])
}

export function shouldShowAppChrome(pathname: string, isAuthenticated: boolean) {
    return (
        isAuthenticated &&
        !isAuthRoute(pathname) &&
        !FULLSCREEN_ROUTES.includes(pathname as (typeof FULLSCREEN_ROUTES)[number])
    )
}

export function getRouteTitle(pathname: string) {
    if (isProductRoute(pathname)) {
        return translate("route.product")
    }

    return translate(headerTitleKeys[pathname] ?? headerTitleKeys[ROUTES.home])
}
