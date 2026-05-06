import type { ReactNode } from "react"

import type { Language, TranslationKey } from "@/i18n/translations"

export type TranslationFn = (key: TranslationKey) => string

export type LanguageContextValue = {
    language: Language
    setLanguage: (language: Language) => void
    t: TranslationFn
    toggleLanguage: () => void
}

export type LanguageProviderProps = {
    children: ReactNode
}
