import { ApiError, apiPost } from "@/services/api/client"
import { ENDPOINTS } from "@/services/api/constants"
import type {
    GuestBasketQuotePayload,
    GuestBasketQuoteRead,
    GuestEmailCheckPayload,
    GuestEmailCheckResponse,
    GuestOrderPayload,
    GuestOrderResponse,
} from "@/services/api/guest.types"

function guestPath(path: string) {
    return `${ENDPOINTS.GUEST}${path}`
}

const PUBLIC_REQUEST_OPTIONS = { auth: false, retryOnUnauthorized: false } as const

export function quoteGuestBasket(payload: GuestBasketQuotePayload): Promise<GuestBasketQuoteRead> {
    return apiPost<GuestBasketQuoteRead, GuestBasketQuotePayload>(
        guestPath("/basket/quote"),
        payload,
        PUBLIC_REQUEST_OPTIONS,
    )
}

export function checkGuestEmail(email: string): Promise<GuestEmailCheckResponse> {
    return apiPost<GuestEmailCheckResponse, GuestEmailCheckPayload>(
        guestPath("/email/check"),
        { email },
        PUBLIC_REQUEST_OPTIONS,
    )
}

export function createGuestOrder(payload: GuestOrderPayload): Promise<GuestOrderResponse> {
    return apiPost<GuestOrderResponse, GuestOrderPayload>(
        guestPath("/orders"),
        payload,
        PUBLIC_REQUEST_OPTIONS,
    )
}

export function isGuestEmailExistsError(error: unknown) {
    if (!(error instanceof ApiError) || error.status !== 409) {
        return false
    }

    const body = error.body
    if (typeof body !== "object" || body === null || !("detail" in body)) {
        return false
    }

    const detail = body.detail
    return (
        typeof detail === "object" &&
        detail !== null &&
        "code" in detail &&
        detail.code === "email_exists"
    )
}
