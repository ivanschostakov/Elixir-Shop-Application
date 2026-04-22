import { useCallback, useMemo, useState } from "react"

import type { ScreenTemplateKind } from "@/components/templates/screen-template.types"
import {
    ScreenTemplateContext,
    type ScreenTemplateProviderProps,
} from "@/providers/screen-template-provider.context"

export function ScreenTemplateProvider({ children }: ScreenTemplateProviderProps) {
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

export { useScreenTemplate } from "@/providers/screen-template-provider.context"
