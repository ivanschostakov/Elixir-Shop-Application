import type { ReactNode } from "react"
import type { StyleProp, ViewStyle } from "react-native"

import type { ScreenChromeTemplateConfig } from "@/components/templates/screen-template.types"

export type StickyFooterProps = {
    template: ScreenChromeTemplateConfig
}

export type StickyFooterSurfaceProps = {
    children: ReactNode
    contentStyle?: StyleProp<ViewStyle>
    style?: StyleProp<ViewStyle>
    variant?: "default" | "search"
}
