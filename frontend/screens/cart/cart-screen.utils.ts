import { ApiError } from "@/services/api/client"

type CartErrorTranslationKey =
    | "cart.itemMissing"
    | "cart.loadFailedMessage"
    | "cart.stockConflict"
    | "cart.updateFailed"

type CartErrorTranslator = (key: CartErrorTranslationKey) => string

export function getBasketErrorMessage(
    error: unknown,
    fallbackMessage: string | null,
    t: CartErrorTranslator,
) {
    if (error instanceof ApiError) {
        if (error.status === 404) {
            return t("cart.itemMissing")
        }

        if (error.status === 409) {
            return t("cart.stockConflict")
        }
    }

    return error instanceof Error ? error.message : fallbackMessage ?? t("cart.updateFailed")
}
