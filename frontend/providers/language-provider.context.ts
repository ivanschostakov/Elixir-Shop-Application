import type { LanguageContextValue } from "@/providers/language-provider.types"

import { translate } from "@/i18n/translations"

export const russianLanguageContext: LanguageContextValue = {
    t: translate,
}

export function useLanguage() {
    return russianLanguageContext
}
