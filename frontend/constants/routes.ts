import { translate, type TranslationKey } from "@/i18n/translations"
import { Href } from "expo-router"

export const ROUTES = {
    home: "/",
    discover: "/discover",
    chat: "/chat",
    basket: "/basket",
    checkout: "/checkout",
    delivery: "/delivery",
    favorites: "/favorites",
    register: "/register",
    login: "/login",
    payment: "/payment",
    profile: "/profile",
    personalData: "/personal-data",
    profileDrafts: "/profile-drafts",
    profileHistory: "/profile-history",
    websiteAccount: "/website-account",
    contacts: "/contacts",
    requisites: "/requisites",
    publicOffer: "/public-offer",
} as const

const PRODUCT_ROUTE_PREFIX = "/products/"

const headerTitleKeys: Record<string, TranslationKey> = {
    [ROUTES.home]: "route.home",
    [ROUTES.discover]: "route.discover",
    [ROUTES.chat]: "route.chat",
    [ROUTES.basket]: "route.basket",
    [ROUTES.checkout]: "route.checkout",
    [ROUTES.delivery]: "route.delivery",
    [ROUTES.favorites]: "route.favorites",
    [ROUTES.payment]: "route.payment",
    [ROUTES.profile]: "route.profile",
    [ROUTES.personalData]: "route.personalData",
    [ROUTES.profileDrafts]: "route.profileDrafts",
    [ROUTES.profileHistory]: "route.profileHistory",
    [ROUTES.websiteAccount]: "route.websiteAccount",
    [ROUTES.contacts]: "route.contacts",
    [ROUTES.requisites]: "route.requisites",
    [ROUTES.publicOffer]: "route.publicOffer",
}

export const PRIMARY_APP_ROUTES = [
    ROUTES.home,
    ROUTES.discover,
    ROUTES.favorites,
    ROUTES.chat,
    ROUTES.basket,
    ROUTES.profile,
] as const

const ACCOUNT_REQUIRED_ROUTES = [
    ROUTES.favorites,
    ROUTES.chat,
    ROUTES.profile,
    ROUTES.personalData,
    ROUTES.profileDrafts,
    ROUTES.profileHistory,
    ROUTES.websiteAccount,
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

export function isAccountRequiredRoute(pathname: string) {
    const normalizedPath = pathname.split("?")[0]
    return ACCOUNT_REQUIRED_ROUTES.includes(normalizedPath as (typeof ACCOUNT_REQUIRED_ROUTES)[number])
}

export function shouldShowAppChrome(pathname: string, _isAuthenticated: boolean) {
    return (
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
