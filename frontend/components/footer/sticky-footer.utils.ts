import { ApiError } from "@/services/api/client"

export function getAddToCartErrorMessage(
    error: unknown,
    fallbackMessage: string | null,
    t: (key: "product.addToCartFailed" | "product.addToCartMissingVariant" | "product.addToCartUnavailable") => string
) {
    if (error instanceof ApiError) {
        if (error.status === 404) {
            return t("product.addToCartMissingVariant")
        }

        if (error.status === 409) {
            return t("product.addToCartUnavailable")
        }
    }

    return error instanceof Error ? error.message : fallbackMessage ?? t("product.addToCartFailed")
}
