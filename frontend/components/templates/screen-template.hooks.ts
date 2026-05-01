import { useLayoutEffect, useRef } from "react"

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
    const stableChromeTemplate = useStableScreenChromeTemplate(chromeTemplate ?? null)

    useLayoutEffect(() => {
        setScreenTemplate(kind)

        return () => {
            setScreenTemplate(null)
        }
    }, [kind, setScreenTemplate])

    useLayoutEffect(() => {
        setScreenChromeTemplate(stableChromeTemplate)

        return () => {
            setScreenChromeTemplate(null)
        }
    }, [setScreenChromeTemplate, stableChromeTemplate])
}

function useStableScreenChromeTemplate(chromeTemplate: ScreenChromeTemplateOverride | null) {
    const chromeTemplateRef = useRef<ScreenChromeTemplateOverride | null>(null)

    if (!areScreenChromeTemplatesEqual(chromeTemplateRef.current, chromeTemplate)) {
        chromeTemplateRef.current = chromeTemplate
    }

    return chromeTemplateRef.current
}

function areScreenChromeTemplatesEqual(
    currentTemplate: ScreenChromeTemplateOverride | null,
    nextTemplate: ScreenChromeTemplateOverride | null,
) {
    if (currentTemplate === nextTemplate) {
        return true
    }

    if (!currentTemplate || !nextTemplate) {
        return false
    }

    return (
        currentTemplate.footer === nextTemplate.footer
        && currentTemplate.header === nextTemplate.header
        && currentTemplate.mode === nextTemplate.mode
        && currentTemplate.title === nextTemplate.title
        && currentTemplate.slots?.footer === nextTemplate.slots?.footer
        && currentTemplate.slots?.headerCenter === nextTemplate.slots?.headerCenter
        && currentTemplate.slots?.headerLeft === nextTemplate.slots?.headerLeft
        && currentTemplate.slots?.headerRight === nextTemplate.slots?.headerRight
    )
}
