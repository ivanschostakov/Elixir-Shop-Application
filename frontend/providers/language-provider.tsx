import { useLanguage } from "@/providers/language-provider.context"
import type { LanguageProviderProps } from "@/providers/language-provider.types"

export function LanguageProvider({ children }: LanguageProviderProps) {
    return <>{children}</>
}

export { useLanguage }
