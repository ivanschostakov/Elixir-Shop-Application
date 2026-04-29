import type { AppHeaderStyles } from "@/components/header/app-header.styles"
import type { LanguageContextValue } from "@/providers/language-provider.types"
import type { ThemeName } from "@/theme/colors"

export type HeaderMenuProps = {
    isOpen: boolean
    onClose: () => void
    onSignOut: () => Promise<void>
    onToggleTheme?: () => void
    onToggle: () => void
    styles: AppHeaderStyles
    t: LanguageContextValue["t"]
    themeName?: ThemeName
}
