import { useLayoutEffect } from "react"

import type {
    ScreenChromeTemplateOverride,
    ScreenTemplateKind,
} from "@/components/templates/screen-template.types"
import { useScreenChromeTemplate } from "@/providers/screen-chrome-template-provider"
import { useScreenTemplate } from "@/providers/screen-template-provider"

export function useApplyScreenTemplate(
    kind: ScreenTemplateKind,
    chromeTemplate?: ScreenChromeTemplateOverride | null,
) {
    const { setScreenChromeTemplate } = useScreenChromeTemplate()
    const { setScreenTemplate } = useScreenTemplate()

    useLayoutEffect(() => {
        setScreenTemplate(kind)

        return () => {
            setScreenTemplate(null)
        }
    }, [kind, setScreenTemplate])

    useLayoutEffect(() => {
        setScreenChromeTemplate(chromeTemplate ?? null)

        return () => {
            setScreenChromeTemplate(null)
        }
    }, [chromeTemplate, setScreenChromeTemplate])
}
