import { useSyncExternalStore } from "react"

import type { DeliveryCountryCode } from "@/services/api/delivery.types"

let selectedDeliveryCountry: DeliveryCountryCode | null = null
const listeners = new Set<() => void>()

function notifyListeners() {
    listeners.forEach((listener) => {
        listener()
    })
}

function subscribeDeliveryCountrySelectionStore(listener: () => void) {
    listeners.add(listener)

    return () => {
        listeners.delete(listener)
    }
}

export function getSelectedDeliveryCountry() {
    return selectedDeliveryCountry
}

export function setSelectedDeliveryCountry(nextDeliveryCountry: DeliveryCountryCode | null) {
    selectedDeliveryCountry = nextDeliveryCountry
    notifyListeners()
}

export function useSelectedDeliveryCountry() {
    return useSyncExternalStore(
        subscribeDeliveryCountrySelectionStore,
        getSelectedDeliveryCountry,
        () => null,
    )
}
