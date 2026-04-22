import type { ReactNode } from "react"
import { createContext, useContext } from "react"

import type { ScreenTemplateKind } from "@/components/templates/screen-template.types"

export type ScreenTemplateContextValue = {
    screenTemplate: ScreenTemplateKind | null
    setScreenTemplate: (screenTemplate: ScreenTemplateKind | null) => void
}

export type ScreenTemplateProviderProps = {
    children: ReactNode
}

export const ScreenTemplateContext = createContext<ScreenTemplateContextValue | null>(null)

export function useScreenTemplate() {
    const context = useContext(ScreenTemplateContext)

    if (!context) {
        throw new Error("useScreenTemplate must be used within a ScreenTemplateProvider")
    }

    return context
}
