import { createContext, useContext } from "react"

import { translate } from "@/i18n/translations"
import type { LanguageContextValue } from "@/providers/language-provider.types"

export const fallbackLanguageContext: LanguageContextValue = {
    language: "ru",
    setLanguage: () => undefined,
    t: translate,
    toggleLanguage: () => undefined,
}

export const LanguageContext = createContext<LanguageContextValue>(fallbackLanguageContext)

export function useLanguage() {
    return useContext(LanguageContext)
}
