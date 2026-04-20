import type { TranslationFn } from "@/providers/language-provider.types"
import type { ProductVariantRead } from "@/types/product"

export function getVariantStockLabel(stock: number, t: TranslationFn) {
    if (stock === 0) {
        return t("product.variantOutOfStock")
    }

    if (stock <= 10) {
        return t("product.variantLowStock")
    }

    return t("product.variantInStock")
}

export function getPreferredVariantId(
    variants: Pick<ProductVariantRead, "id" | "stock">[],
    rememberedVariantId: number | undefined,
) {
    const rememberedVariant = variants.find((variant) => variant.id === rememberedVariantId)

    if (rememberedVariant && rememberedVariant.stock > 0) {
        return rememberedVariant.id
    }

    const firstAvailableVariant = variants.find((variant) => variant.stock > 0)

    if (firstAvailableVariant) {
        return firstAvailableVariant.id
    }

    return rememberedVariant?.id ?? variants[0]?.id ?? null
}
