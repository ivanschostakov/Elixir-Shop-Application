import type { ReactNode } from "react"
import type { StyleProp, ViewStyle } from "react-native"

export type AppChromeHeaderTemplate = "title" | "tabs" | "search" | "overlay" | "none"
export type AppChromeFooterTemplate = "nav" | "nav+productAction" | "nav+basketAction" | "customSurface" | "none"
export type AppChromeMode = "standard" | "fullscreen"

export type ScreenTemplateKind = "feed" | "catalog" | "detail" | "map-flow"

export type ScreenChromeTemplateSlots = {
    footer?: ReactNode
    headerCenter?: ReactNode
    headerRight?: ReactNode
}

export type ScreenChromeTemplateConfig = {
    footer: AppChromeFooterTemplate
    header: AppChromeHeaderTemplate
    mode: AppChromeMode
    slots?: ScreenChromeTemplateSlots
    title?: string | null
}

export type ScreenChromeTemplateOverride = Partial<Omit<ScreenChromeTemplateConfig, "slots">> & {
    slots?: Partial<ScreenChromeTemplateSlots>
}

export type TemplateContainerProps = {
    children: ReactNode
    chromeTemplate?: ScreenChromeTemplateOverride | null
    style?: StyleProp<ViewStyle>
}

export type FeedTemplateProps = TemplateContainerProps & {
    contentContainerStyle?: StyleProp<ViewStyle>
    scrollViewStyle?: StyleProp<ViewStyle>
    showsVerticalScrollIndicator?: boolean
}

export type MapFlowTemplateProps = {
    children: ReactNode
    chromeOverlay?: ReactNode
    overlay?: ReactNode
    style?: StyleProp<ViewStyle>
}
