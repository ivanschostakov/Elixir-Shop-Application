import type { ProductRead, ProductWithVariantsRead } from "@/types/product"

const decodeHtmlEntities = (value: string) =>
    value
        .replace(/&nbsp;/gi, " ")
        .replace(/&amp;/gi, "&")
        .replace(/&quot;/gi, '"')
        .replace(/&#39;|&apos;/gi, "'")
        .replace(/&lt;/gi, "<")
        .replace(/&gt;/gi, ">")

export const getPlainTextContent = (value?: string | null) => {
    if (!value) {
        return null
    }

    const plainText = decodeHtmlEntities(
        value
            .replace(/<script[\s\S]*?<\/script>/gi, " ")
            .replace(/<style[\s\S]*?<\/style>/gi, " ")
            .replace(/<[^>]+>/g, " ")
            .replace(/\s+/g, " ")
            .trim()
    )

    return plainText || null
}

type ProductTextSource = Pick<ProductRead, "description" | "sku">

const getNumericPrice = (value?: number | string | null) => {
    if (value === null || value === undefined || value === "") {
        return null
    }

    const numericPrice = typeof value === "string" ? Number(value) : value

    return Number.isFinite(numericPrice) ? numericPrice : null
}

export const formatProductPrice = (value?: number | string | null) => {
    const numericPrice = getNumericPrice(value)

    if (numericPrice === null) {
        return null
    }

    const hasFraction = Math.round(numericPrice * 100) % 100 !== 0

    return `${new Intl.NumberFormat("RU", {
        maximumFractionDigits: hasFraction ? 2 : 0,
        minimumFractionDigits: 0,
    }).format(numericPrice)} ₽`
}

const getProductDisplayPrice = (product: Pick<ProductWithVariantsRead, "variants">) => {
    const prices = product.variants
        .map((variant) => getNumericPrice(variant.price))
        .filter((price): price is number => price !== null)

    if (prices.length === 0) {
        return null
    }

    return Math.min(...prices)
}

export const getProductPriceLabel = (product: Pick<ProductWithVariantsRead, "variants">) => {
    const numericPrice = getProductDisplayPrice(product)
    const formattedPrice = formatProductPrice(numericPrice)

    return formattedPrice ? `от ${formattedPrice}` : null
}

export function isProductOutOfStock(product: Pick<ProductWithVariantsRead, "variants">) {
    return !product.variants.some((variant) => variant.stock > 0)
}

export function getProductContentSubtitle(product: ProductTextSource) {
    const trimmedDescription = getPlainTextContent(product.description)

    return trimmedDescription ? trimmedDescription : product.sku
}
