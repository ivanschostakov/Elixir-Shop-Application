import type { AppHeaderStyles } from "@/components/header/app-header.styles"
import type { LanguageContextValue } from "@/providers/language-provider.types"

export type HeaderSearchPanelProps = {
    onClose: () => void
    pathname: string
    styles: AppHeaderStyles
    t: LanguageContextValue["t"]
    visible: boolean
}
