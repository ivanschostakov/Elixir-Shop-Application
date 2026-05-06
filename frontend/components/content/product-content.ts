import type { ProductRead, ProductVariantRead, ProductWithVariantsRead } from "@/types/product"

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

export type ProductPriceDisplay = {
    currentLabel: string
    originalLabel: string | null
    discountLabel: string | null
    hasDiscount: boolean
    prefix: string
}

type ProductPriceDisplayCandidate = ProductPriceDisplay & {
    currentPrice: number
}

export function getVariantPriceDisplay(variant?: ProductVariantRead | null, prefix = ""): ProductPriceDisplay | null {
    if (!variant) {
        return null
    }

    const originalPrice = getNumericPrice(variant.original_price ?? variant.price)
    const discountedPrice = getNumericPrice(variant.discounted_price ?? variant.price)
    if (originalPrice === null || discountedPrice === null) {
        return null
    }

    const discountPercent = getNumericPrice(variant.discount_percent)
    const hasDiscount = Boolean(discountPercent && discountPercent > 0 && discountedPrice < originalPrice)
    const currentLabel = formatProductPrice(hasDiscount ? discountedPrice : originalPrice)
    if (!currentLabel) {
        return null
    }

    return {
        currentLabel,
        originalLabel: hasDiscount ? formatProductPrice(originalPrice) : null,
        discountLabel: hasDiscount ? `-${Math.round(discountPercent ?? 0)}%` : null,
        hasDiscount,
        prefix,
    }
}

const getVariantPriceDisplayCandidate = (variant: ProductVariantRead, prefix: string): ProductPriceDisplayCandidate | null => {
    const display = getVariantPriceDisplay(variant, prefix)
    const currentPrice = getNumericPrice(variant.discounted_price ?? variant.price)
    if (!display || currentPrice === null) {
        return null
    }

    return {
        ...display,
        currentPrice,
    }
}

export const getProductPriceDisplay = (product: Pick<ProductWithVariantsRead, "variants">): ProductPriceDisplay | null => {
    const candidates = product.variants
        .map((variant) => getVariantPriceDisplayCandidate(variant, "от "))
        .filter((candidate): candidate is ProductPriceDisplayCandidate => candidate !== null)
        .sort((left, right) => left.currentPrice - right.currentPrice)

    return candidates[0] ?? null
}

export const getProductPriceLabel = (product: Pick<ProductWithVariantsRead, "variants">) => {
    const priceDisplay = getProductPriceDisplay(product)

    return priceDisplay ? `${priceDisplay.prefix}${priceDisplay.currentLabel}` : null
}

export function isProductOutOfStock(product: Pick<ProductWithVariantsRead, "variants">) {
    return !product.variants.some((variant) => variant.stock > 0)
}

export function getProductContentSubtitle(product: ProductTextSource) {
    const trimmedDescription = getPlainTextContent(product.description)

    return trimmedDescription ? trimmedDescription : product.sku
}
