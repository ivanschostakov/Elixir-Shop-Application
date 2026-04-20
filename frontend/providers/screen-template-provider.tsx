import type { ReactNode } from "react"
import { createContext, useCallback, useContext, useMemo, useState } from "react"

import type { ScreenTemplateKind } from "@/components/templates/screen-template.types"

type ScreenTemplateContextValue = {
    screenTemplate: ScreenTemplateKind | null
    setScreenTemplate: (screenTemplate: ScreenTemplateKind | null) => void
}

const ScreenTemplateContext = createContext<ScreenTemplateContextValue | null>(null)

export function ScreenTemplateProvider({ children }: { children: ReactNode }) {
    const [screenTemplate, setScreenTemplateState] = useState<ScreenTemplateKind | null>(null)

    const setScreenTemplate = useCallback((nextScreenTemplate: ScreenTemplateKind | null) => {
        setScreenTemplateState(nextScreenTemplate)
    }, [])

    const value = useMemo(
        () => ({
            screenTemplate,
            setScreenTemplate,
        }),
        [screenTemplate, setScreenTemplate],
    )

    return <ScreenTemplateContext.Provider value={value}>{children}</ScreenTemplateContext.Provider>
}

export function useScreenTemplate() {
    const context = useContext(ScreenTemplateContext)

    if (!context) {
        throw new Error("useScreenTemplate must be used within a ScreenTemplateProvider")
    }

    return context
}
