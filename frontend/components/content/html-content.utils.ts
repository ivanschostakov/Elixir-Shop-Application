import { HTML_TAG_PATTERN } from "@/components/content/html-content.const"

export const stripEmbeddedProductCode = (value: string) => value
    .replace(/<(script|style|template|noscript)\b[^>]*>[\s\S]*?(?:<\/\1\s*>|$)/gi, "")
    .replace(/&lt;(script|style|template|noscript)\b[\s\S]*?&gt;[\s\S]*?(?:&lt;\/\1\s*&gt;|$)/gi, "")
    .replace(/\(\s*function\s*\(\s*\)\s*\{\s*var\s+items\s*=\s*document\.querySelectorAll\s*\([\s\S]*?\}\s*\)\s*\(\s*\)\s*;?/gi, "")

const escapeHtml = (value: string) =>
    value
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;")

const stripHtml = (value: string) =>
    stripEmbeddedProductCode(value)
        .replace(/<[^>]+>/g, " ")
        .replace(/&nbsp;/gi, " ")
        .replace(/\s+/g, " ")
        .trim()

export const hasRenderableHtmlContent = (value?: string | null) =>
    Boolean(value && stripHtml(value).length > 0)

export const normalizeHtml = (value: string) => {
    const trimmedValue = stripEmbeddedProductCode(value).trim()

    if (!HTML_TAG_PATTERN.test(trimmedValue)) {
        return `<div><p>${escapeHtml(trimmedValue).replace(/\r?\n/g, "<br />")}</p></div>`
    }

    return `<div>${trimmedValue}</div>`
}
