import { createElement } from "react"
import { Image } from "react-native"
import { LottieView as WebLottieView } from "lottie-react-native/lib/module/LottieView/index.web"

import { contentStyles } from "@/components/content/content.styles"
import { emptyStateWebStyles } from "@/components/content/empty-state.web.styles"
import { isLottieSticker } from "@/components/content/empty-state.web.const"
import type { EmptyStateProps } from "@/components/content/empty-state.types"

export function renderSticker(sticker: NonNullable<EmptyStateProps["sticker"]>, illustrationSize: number) {
    if (isLottieSticker(sticker)) {
        return createElement(WebLottieView, {
            autoPlay: true,
            loop: true,
            source: sticker.source,
            style: emptyStateWebStyles.fill,
            webStyle: emptyStateWebStyles.fill,
        })
    }

    return createElement(Image, {
        source: sticker.source,
        style: [
            contentStyles.emptyStateIllustration,
            emptyStateWebStyles.webIllustration,
            { maxWidth: illustrationSize, maxHeight: illustrationSize },
        ],
        resizeMode: "contain",
    })
}
