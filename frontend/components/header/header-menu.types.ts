import type { StyleProp, ViewStyle } from "react-native"

import type { AppHeaderStyles } from "@/components/header/app-header.styles"
import type { Language } from "@/i18n/translations"
import type { LanguageContextValue } from "@/providers/language-provider.types"
import type { ThemeName } from "@/theme/colors"

export type HeaderMenuContentProps = {
    isAuthenticated: boolean
    onClose: () => void
    onOpenContacts: () => void
    onOpenPublicOffer: () => void
    onOpenRequisites: () => void
    onSignIn: () => void
    onSignOut: () => Promise<void>
    onSetLanguage?: (language: Language) => void
    onToggleTheme?: () => void
    styles: AppHeaderStyles
    t: LanguageContextValue["t"]
    language?: Language
    accentColor?: string
    popupStyle?: StyleProp<ViewStyle>
    themeName?: ThemeName
}

export type HeaderMenuProps = HeaderMenuContentProps & {
    isOpen: boolean
    onToggle: () => void
    renderPopup?: boolean
}
