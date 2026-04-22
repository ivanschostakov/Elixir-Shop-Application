import type { ImageSourcePropType } from "react-native"

import type { DeliveryInfoRow } from "@/screens/delivery/delivery-screen.types"

export type DeliveryProviderOption = {
    imageAlt?: string
    imageSource?: ImageSourcePropType
    key: string
    label: string
}

export type PickupPointFooterExtensionProps = {
    actionLabel?: string
    error?: string | null
    inset?: boolean
    isResolving?: boolean
    isProviderSelectionDisabled?: boolean
    onChoose: () => void
    onClose: () => void
    onCopyInfo: (value: string) => void
    onOpenOfficePage?: (() => void) | null
    onSelectProvider?: ((providerKey: string) => void) | null
    providerOptions?: DeliveryProviderOption[]
    rows: DeliveryInfoRow[]
    selectedProviderKey?: string | null
    title: string
}
