import { useSyncExternalStore } from "react"

let deliveryCountryPickerFocusRequest = 0
const listeners = new Set<() => void>()

function notifyListeners() {
    listeners.forEach((listener) => {
        listener()
    })
}

function subscribeDeliveryCountryPickerFocusStore(listener: () => void) {
    listeners.add(listener)

    return () => {
        listeners.delete(listener)
    }
}

function getDeliveryCountryPickerFocusRequest() {
    return deliveryCountryPickerFocusRequest
}

export function requestDeliveryCountryPickerFocus() {
    deliveryCountryPickerFocusRequest += 1
    notifyListeners()
}

export function useDeliveryCountryPickerFocusRequest() {
    return useSyncExternalStore(
        subscribeDeliveryCountryPickerFocusStore,
        getDeliveryCountryPickerFocusRequest,
        () => 0,
    )
}
