import type { DeliveryPointMarkerWithProvider } from "@/services/api/delivery.types"

export type UseDeliveryPointMarkersState = {
    deliveryPointMarkers: DeliveryPointMarkerWithProvider[]
    isLoading: boolean
    error: string | null
}
