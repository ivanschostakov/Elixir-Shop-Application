import type { ReactNode } from "react"
import { createContext, useCallback, useContext, useMemo, useState } from "react"

import type { ScreenChromeTemplateOverride } from "@/components/templates/screen-template.types"

type ScreenChromeTemplateContextValue = {
    screenChromeTemplate: ScreenChromeTemplateOverride | null
    setScreenChromeTemplate: (screenChromeTemplate: ScreenChromeTemplateOverride | null) => void
}

const ScreenChromeTemplateContext = createContext<ScreenChromeTemplateContextValue | null>(null)

export function ScreenChromeTemplateProvider({ children }: { children: ReactNode }) {
    const [screenChromeTemplate, setScreenChromeTemplateState] =
        useState<ScreenChromeTemplateOverride | null>(null)

    const setScreenChromeTemplate = useCallback((nextScreenChromeTemplate: ScreenChromeTemplateOverride | null) => {
        setScreenChromeTemplateState(nextScreenChromeTemplate)
    }, [])

    const value = useMemo(
        () => ({
            screenChromeTemplate,
            setScreenChromeTemplate,
        }),
        [screenChromeTemplate, setScreenChromeTemplate],
    )

    return (
        <ScreenChromeTemplateContext.Provider value={value}>
            {children}
        </ScreenChromeTemplateContext.Provider>
    )
}

export function useScreenChromeTemplate() {
    const context = useContext(ScreenChromeTemplateContext)

    if (!context) {
        throw new Error("useScreenChromeTemplate must be used within a ScreenChromeTemplateProvider")
    }

    return context
}
