import { useSyncExternalStore } from "react"

import type { SelectedDeliveryAddress } from "@/hooks/delivery/delivery-address-selection-store.types"

let selectedDeliveryAddress: SelectedDeliveryAddress | null = null
const listeners = new Set<() => void>()

function notifyListeners() {
    listeners.forEach((listener) => {
        listener()
    })
}

function subscribeDeliveryAddressSelectionStore(listener: () => void) {
    listeners.add(listener)

    return () => {
        listeners.delete(listener)
    }
}

export function getSelectedDeliveryAddress() {
    return selectedDeliveryAddress
}

export function setSelectedDeliveryAddress(nextDeliveryAddress: SelectedDeliveryAddress | null) {
    selectedDeliveryAddress = nextDeliveryAddress
    notifyListeners()
}

export function useSelectedDeliveryAddress() {
    return useSyncExternalStore(
        subscribeDeliveryAddressSelectionStore,
        getSelectedDeliveryAddress,
        () => null,
    )
}
