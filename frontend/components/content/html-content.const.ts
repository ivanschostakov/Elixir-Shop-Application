import type { ThemePalette } from "@/theme/colors"
import { spacing } from "@/theme/spacing"

import type { HtmlContentVariant, VariantTextStyle } from "@/components/content/html-content.types"

export const HTML_IGNORED_TAGS = [
    "button",
    "embed",
    "form",
    "head",
    "iframe",
    "img",
    "input",
    "link",
    "meta",
    "object",
    "script",
    "select",
    "style",
    "textarea",
    "title",
]

export const SAFE_LINK_SCHEME = /^(https?:|mailto:|tel:)/i
export const HTML_TAG_PATTERN = /<\/?[a-z][\s\S]*>/i

const createVariantStyles = (colors: ThemePalette): Record<HtmlContentVariant, VariantTextStyle> => ({
    summary: {
        color: colors.mutedText,
        fontSize: 15,
        lineHeight: 24,
    },
    body: {
        color: colors.mutedText,
        fontSize: 16,
        lineHeight: 24,
    },
    detail: {
        color: colors.text,
        fontSize: 16,
        lineHeight: 24,
    },
})

const createTagStyles = (colors: ThemePalette, { color, fontSize, lineHeight }: VariantTextStyle) => ({
    a: {
        color: colors.primary,
        textDecorationLine: "underline" as const,
    },
    b: {
        fontWeight: "700" as const,
    },
    blockquote: {
        borderLeftColor: colors.border,
        borderLeftWidth: 3,
        color,
        marginTop: 0,
        marginBottom: spacing.sm,
        paddingLeft: spacing.md,
    },
    div: {
        color,
        fontSize,
        lineHeight,
        marginTop: 0,
        marginBottom: 0,
    },
    em: {
        fontStyle: "italic" as const,
    },
    h1: {
        color: colors.text,
        fontSize: fontSize + 10,
        fontWeight: "800" as const,
        lineHeight: lineHeight + 8,
        marginTop: 0,
        marginBottom: spacing.sm,
    },
    h2: {
        color: colors.text,
        fontSize: fontSize + 8,
        fontWeight: "800" as const,
        lineHeight: lineHeight + 6,
        marginTop: 0,
        marginBottom: spacing.sm,
    },
    h3: {
        color: colors.text,
        fontSize: fontSize + 4,
        fontWeight: "700" as const,
        lineHeight: lineHeight + 4,
        marginTop: 0,
        marginBottom: spacing.xs,
    },
    i: {
        fontStyle: "italic" as const,
    },
    li: {
        color,
        fontSize,
        lineHeight,
        marginBottom: spacing.xs,
    },
    ol: {
        marginTop: 0,
        marginBottom: spacing.sm,
        paddingLeft: spacing.lg,
    },
    p: {
        color,
        fontSize,
        lineHeight,
        marginTop: 0,
        marginBottom: spacing.sm,
    },
    span: {
        color,
        fontSize,
        lineHeight,
    },
    strong: {
        fontWeight: "700" as const,
    },
    ul: {
        marginTop: 0,
        marginBottom: spacing.sm,
        paddingLeft: spacing.lg,
    },
})

export const createHtmlContentStyles = (colors: ThemePalette) => {
    const variantStyles = createVariantStyles(colors)

    return {
        variantStyles,
        variantTagStyles: {
            summary: createTagStyles(colors, variantStyles.summary),
            body: createTagStyles(colors, variantStyles.body),
            detail: createTagStyles(colors, variantStyles.detail),
        },
    }
}
