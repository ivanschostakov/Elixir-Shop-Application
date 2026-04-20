export type HtmlContentVariant = "summary" | "body" | "detail"

export type VariantTextStyle = {
    color: string
    fontSize: number
    lineHeight: number
}

export type HtmlContentProps = {
    html: string
    variant?: HtmlContentVariant
}
