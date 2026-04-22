import type { InitialRegion, Point } from "react-native-yamap"

import type { DeliveryCountryCode, DeliveryPointProvider } from "@/services/api/delivery.types"
import type { SelectedDeliveryAddress } from "@/hooks/delivery/delivery-address-selection-store.types"
import type { SelectedDeliveryPoint } from "@/hooks/delivery/delivery-point-selection-store.types"

export type DeliveryLocationState = {
    detectedCountryCode: DeliveryCountryCode | null
    hasUserLocation: boolean
    isResolvingLocation: boolean
    requestUserLocation: () => Promise<Point | null>
    userPoint: Point
}

export type DeliveryMode = "pickup" | "door"

export type DeliveryMapMarker =
    | {
          iconKey: string
          point: Point
          data: {
              code: string
              kind: "pickup"
              provider: DeliveryPointProvider
          }
      }
    | {
          point: Point
          data: {
              kind: "door"
          }
      }

export type DeliveryDoorDraft = SelectedDeliveryAddress

export type DeliveryPickupDraft = SelectedDeliveryPoint & {
    nearest_metro_station?: string | null
    nearest_station?: string | null
    note?: string | null
    emails?: string[]
    phones?: string[]
}

export type DeliveryInfoRow = {
    key: string
    label: string
    value: string
}

export type DeliveryCameraCommand =
    | {
          duration: number
          id: number
          kind: "region"
          region: InitialRegion
      }

export type DeliveryMapCameraState = {
    handleMapLoaded: () => void
    moveToRegion: (region: InitialRegion, duration?: number) => void
}
