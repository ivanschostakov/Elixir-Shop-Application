import { translate } from "@/i18n/translations"
import type { LanguageContextValue, LanguageProviderProps } from "@/providers/language-provider.types"

const russianLanguageContext: LanguageContextValue = {
    t: translate,
}

export function LanguageProvider({ children }: LanguageProviderProps) {
    return <>{children}</>
}

export function useLanguage() {
    return russianLanguageContext
}
