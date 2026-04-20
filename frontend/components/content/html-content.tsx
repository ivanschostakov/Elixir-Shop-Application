import { useMemo } from "react"
import { Linking, Platform, useWindowDimensions } from "react-native"
import RenderHtml from "react-native-render-html"

import {
    HTML_IGNORED_TAGS,
    SAFE_LINK_SCHEME,
    variantStyles,
    variantTagStyles,
} from "@/components/content/html-content.const"
import type { HtmlContentProps } from "@/components/content/html-content.types"
import { hasRenderableHtmlContent, normalizeHtml } from "@/components/content/html-content.utils"

export { hasRenderableHtmlContent }

export function HtmlContent({ html, variant = "body" }: HtmlContentProps) {
    const { width } = useWindowDimensions()
    const source = useMemo(() => ({ html: normalizeHtml(html) }), [html])

    return (
        <RenderHtml
            baseStyle={variantStyles[variant]}
            contentWidth={Math.max(width, 1)}
            dangerouslyDisableHoisting={Platform.OS === "web"}
            enableCSSInlineProcessing={false}
            enableUserAgentStyles={false}
            ignoredDomTags={HTML_IGNORED_TAGS}
            renderersProps={{
                a: {
                    onPress: (_, href) => {
                        if (!SAFE_LINK_SCHEME.test(href)) {
                            return
                        }

                        void Linking.openURL(href).catch(() => undefined)
                    },
                },
            }}
            source={source}
            tagsStyles={variantTagStyles[variant]}
        />
    )
}
