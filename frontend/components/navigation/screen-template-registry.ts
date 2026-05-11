import type {
    ScreenChromeTemplateConfig,
    ScreenChromeTemplateOverride,
    ScreenTemplateKind,
} from "@/components/templates/screen-template.types"
import { ROUTES, getRouteTitle, isAuthRoute, isProductRoute } from "@/constants/routes"

export function getDefaultScreenTemplateKind(pathname: string): ScreenTemplateKind {
    if (pathname === ROUTES.delivery) {
        return "map-flow"
    }

    if (pathname === ROUTES.home || pathname === ROUTES.discover || pathname === ROUTES.favorites) {
        return "catalog"
    }

    if (isProductRoute(pathname)) {
        return "detail"
    }

    return "feed"
}

export function getDefaultScreenChromeTemplate(
    pathname: string,
    _isAuthenticated: boolean,
): ScreenChromeTemplateConfig {
    const title = getRouteTitle(pathname)

    if (isAuthRoute(pathname)) {
        return {
            footer: "none",
            header: "none",
            mode: "standard",
            title,
        }
    }

    if (pathname === ROUTES.delivery) {
        return {
            footer: "none",
            header: "none",
            mode: "fullscreen",
            title,
        }
    }

    if (pathname === ROUTES.home) {
        return {
            footer: "nav",
            header: "none",
            mode: "standard",
            title,
        }
    }

    if (isProductRoute(pathname)) {
        return {
            footer: "nav+productAction",
            header: "overlay",
            mode: "standard",
            title,
        }
    }

    if (pathname === ROUTES.basket) {
        return {
            footer: "nav+basketAction",
            header: "title",
            mode: "standard",
            title,
        }
    }

    if (pathname === ROUTES.discover || pathname === ROUTES.favorites) {
        return {
            footer: "nav",
            header: "tabs",
            mode: "standard",
            title,
        }
    }

    return {
        footer: "nav",
        header: "title",
        mode: "standard",
        title,
    }
}

export function mergeScreenChromeTemplate(
    baseTemplate: ScreenChromeTemplateConfig,
    overrideTemplate: ScreenChromeTemplateOverride | null,
): ScreenChromeTemplateConfig {
    if (!overrideTemplate) {
        return baseTemplate
    }

    return {
        ...baseTemplate,
        ...overrideTemplate,
        slots: {
            ...baseTemplate.slots,
            ...overrideTemplate.slots,
        },
        title: overrideTemplate.title === undefined ? baseTemplate.title : overrideTemplate.title,
    }
}
