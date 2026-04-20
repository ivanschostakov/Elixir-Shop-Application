import { useSyncExternalStore } from "react"

import type { SelectedDeliveryPoint } from "@/hooks/delivery/delivery-point-selection-store.types"

let selectedDeliveryPoint: SelectedDeliveryPoint | null = null
const listeners = new Set<() => void>()

function notifyListeners() {
    listeners.forEach((listener) => {
        listener()
    })
}

function subscribeDeliveryPointSelectionStore(listener: () => void) {
    listeners.add(listener)

    return () => {
        listeners.delete(listener)
    }
}

export function getSelectedDeliveryPoint() {
    return selectedDeliveryPoint
}

export function setSelectedDeliveryPoint(nextDeliveryPoint: SelectedDeliveryPoint | null) {
    selectedDeliveryPoint = nextDeliveryPoint
    notifyListeners()
}

export function useSelectedDeliveryPoint() {
    return useSyncExternalStore(
        subscribeDeliveryPointSelectionStore,
        getSelectedDeliveryPoint,
        () => null,
    )
}
