import { HTML_TAG_PATTERN } from "@/components/content/html-content.const"

const escapeHtml = (value: string) =>
    value
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;")

const stripHtml = (value: string) =>
    value
        .replace(/<script[\s\S]*?<\/script>/gi, " ")
        .replace(/<style[\s\S]*?<\/style>/gi, " ")
        .replace(/<[^>]+>/g, " ")
        .replace(/&nbsp;/gi, " ")
        .replace(/\s+/g, " ")
        .trim()

export const hasRenderableHtmlContent = (value?: string | null) =>
    Boolean(value && stripHtml(value).length > 0)

export const normalizeHtml = (value: string) => {
    const trimmedValue = value.trim()

    if (!HTML_TAG_PATTERN.test(trimmedValue)) {
        return `<div><p>${escapeHtml(trimmedValue).replace(/\r?\n/g, "<br />")}</p></div>`
    }

    return `<div>${trimmedValue}</div>`
}
