import { useCallback, useMemo, useState } from "react"

import type { ScreenChromeTemplateOverride } from "@/components/templates/screen-template.types"
import {
    ScreenChromeTemplateContext,
    type ScreenChromeTemplateProviderProps,
} from "@/providers/screen-chrome-template-provider.context"

export function ScreenChromeTemplateProvider({ children }: ScreenChromeTemplateProviderProps) {
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

export { useScreenChromeTemplate } from "@/providers/screen-chrome-template-provider.context"
