import type { AppHeaderStyles } from "@/components/header/app-header.styles"
import type { Language } from "@/i18n/translations"
import type { LanguageContextValue } from "@/providers/language-provider.types"
import type { ThemeName } from "@/theme/colors"

export type HeaderMenuProps = {
    isOpen: boolean
    isAuthenticated: boolean
    onClose: () => void
    onOpenContacts: () => void
    onOpenPublicOffer: () => void
    onOpenRequisites: () => void
    onSignIn: () => void
    onSignOut: () => Promise<void>
    onToggleLanguage?: () => void
    onToggleTheme?: () => void
    onToggle: () => void
    styles: AppHeaderStyles
    t: LanguageContextValue["t"]
    language?: Language
    themeName?: ThemeName
}
