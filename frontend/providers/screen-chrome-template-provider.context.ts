import type { ReactNode } from "react"
import { createContext, useContext } from "react"

import type { ScreenChromeTemplateOverride } from "@/components/templates/screen-template.types"

export type ScreenChromeTemplateContextValue = {
    screenChromeTemplate: ScreenChromeTemplateOverride | null
    setScreenChromeTemplate: (screenChromeTemplate: ScreenChromeTemplateOverride | null) => void
}

export type ScreenChromeTemplateProviderProps = {
    children: ReactNode
}

export const ScreenChromeTemplateContext = createContext<ScreenChromeTemplateContextValue | null>(null)

export function useScreenChromeTemplate() {
    const context = useContext(ScreenChromeTemplateContext)

    if (!context) {
        throw new Error("useScreenChromeTemplate must be used within a ScreenChromeTemplateProvider")
    }

    return context
}
