import type { DeliveryGeoSuggestResult } from "@/services/api/delivery.types"

export type DeliverySearchPanelProps = {
    autoFocus?: boolean
    error?: string | null
    isLoading?: boolean
    onChangeText: (value: string) => void
    onClose?: () => void
    onFocusChange?: (isFocused: boolean) => void
    onSubmitSearch?: () => void
    onSelectResult: (result: DeliveryGeoSuggestResult) => void
    results: DeliveryGeoSuggestResult[]
    value: string
    variant?: "floating" | "footer"
}
