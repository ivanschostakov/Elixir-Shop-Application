import type { StickerConfig } from "@/constants/stickers"

import { WEB_BREAKPOINTS } from "@/components/content/empty-state.web.styles"

export function getIllustrationSize(windowWidth: number) {
    if (windowWidth >= WEB_BREAKPOINTS.lg) {
        return 220
    }

    if (windowWidth >= WEB_BREAKPOINTS.md) {
        return 190
    }

    if (windowWidth >= WEB_BREAKPOINTS.sm) {
        return 160
    }

    return 132
}

export function isLottieSticker(sticker: StickerConfig) {
    return sticker.kind === "lottie"
}
