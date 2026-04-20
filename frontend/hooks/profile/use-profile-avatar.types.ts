import type { TranslationKey } from "@/i18n/translations"

export type UseProfileAvatarParams = {
    userId?: number
    t: (key: TranslationKey) => string
}
