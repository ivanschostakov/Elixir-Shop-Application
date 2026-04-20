import type { AppHeaderStyles } from "@/components/header/app-header.styles"
import type { LanguageContextValue } from "@/providers/language-provider.types"

export type HeaderMenuProps = {
    isOpen: boolean
    onClose: () => void
    onSignOut: () => Promise<void>
    onToggle: () => void
    styles: AppHeaderStyles
    t: LanguageContextValue["t"]
}
