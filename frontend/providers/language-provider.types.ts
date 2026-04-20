import type { ReactNode } from "react"

import type { TranslationKey } from "@/i18n/translations"

export type TranslationFn = (key: TranslationKey) => string

export type LanguageContextValue = {
    t: TranslationFn
}

export type LanguageProviderProps = {
    children: ReactNode
}
