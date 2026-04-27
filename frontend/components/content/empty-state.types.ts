import type { ReactNode } from "react"

import type { StickerConfig } from "@/constants/stickers"

export type EmptyStateProps = {
    title?: string
    description?: string
    eyebrow?: string
    actionLabel?: string
    onPressAction?: () => void
    sticker?: StickerConfig
    illustration?: ReactNode
    variant?: "card" | "plain"
    actionVariant?: "button" | "link"
}
