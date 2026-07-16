import { createElement } from "react"
import { Image, type ImageStyle, type StyleProp } from "react-native"
import { LottieView as WebLottieView } from "lottie-react-native/lib/module/LottieView/index.web"

import { emptyStateWebStyles } from "@/components/content/empty-state.web.styles"
import { isLottieSticker } from "@/components/content/empty-state.web.const"
import type { EmptyStateProps } from "@/components/content/empty-state.types"

export function renderSticker(
    sticker: NonNullable<EmptyStateProps["sticker"]>,
    illustrationSize: number,
    illustrationStyle: StyleProp<ImageStyle>,
) {
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
            illustrationStyle,
            emptyStateWebStyles.webIllustration,
            { maxWidth: illustrationSize, maxHeight: illustrationSize },
        ],
        resizeMode: "contain",
    })
}
