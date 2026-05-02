import { useMemo, useState } from "react"
import type { Point } from "react-native-yamap"

import { DEFAULT_DELIVERY_COUNTRY_CODE } from "@/services/api/delivery"
import { DOOR_DELIVERY_PROVIDER, supportsDoorDeliveryForCountry } from "@/screens/delivery/delivery-screen.constants"
import type { DeliveryDoorDraft, DeliveryPickupDraft } from "@/screens/delivery/delivery-screen.types"
import { buildPickupPointDraft, getDoorDeliveryPoint, getPickupPoint } from "@/screens/delivery/delivery-screen.utils"
import { useDeliveryGeoSearch } from "@/hooks/delivery/use-delivery-geo-search"
import type { SelectedDeliveryAddress } from "@/hooks/delivery/delivery-address-selection-store.types"
import type { SelectedDeliveryPoint } from "@/hooks/delivery/delivery-point-selection-store.types"
import type { DeliveryCountryCode } from "@/services/api/delivery.types"

type UseDeliveryFlowControllerParams = {
    selectedDeliveryAddress: SelectedDeliveryAddress | null
    selectedDeliveryCountry: DeliveryCountryCode | null
    selectedDeliveryPoint: SelectedDeliveryPoint | null
    userPoint: Point
    searchPanelExpanded?: boolean
}

export function useDeliveryFlowController({
    selectedDeliveryAddress,
    selectedDeliveryCountry,
    selectedDeliveryPoint,
    userPoint,
    searchPanelExpanded = false,
}: UseDeliveryFlowControllerParams) {
    const activeCountryCode = selectedDeliveryCountry ?? DEFAULT_DELIVERY_COUNTRY_CODE
    const supportsDoorDelivery = supportsDoorDeliveryForCountry(activeCountryCode)

    const [searchFocusPoint, setSearchFocusPoint] = useState<Point | null>(null)
    const [isSearchFocused, setIsSearchFocused] = useState(false)
    const [search, setSearch] = useState("")
    const [searchEnabled, setSearchEnabled] = useState(true)

    const [doorDeliveryDraft, setDoorDeliveryDraft] = useState<DeliveryDoorDraft | null>(
        selectedDeliveryAddress
            ? {
                  ...selectedDeliveryAddress,
                  provider: DOOR_DELIVERY_PROVIDER,
              }
            : null,
    )
    const [isDoorFooterExpanded, setIsDoorFooterExpanded] = useState(Boolean(selectedDeliveryAddress))

    const [pickupPointDraft, setPickupPointDraft] = useState<DeliveryPickupDraft | null>(
        selectedDeliveryPoint ? buildPickupPointDraft(selectedDeliveryPoint) : null,
    )
    const [isPickupFooterExpanded, setIsPickupFooterExpanded] = useState(Boolean(selectedDeliveryPoint))

    const [isResolvingDoorAddress, setIsResolvingDoorAddress] = useState(false)
    const [isResolvingPickupPoint, setIsResolvingPickupPoint] = useState(false)
    const [removedDeliveryPointKeys, setRemovedDeliveryPointKeys] = useState<Set<string>>(() => new Set())
    const [selectionError, setSelectionError] = useState<string | null>(null)
    const [pickupPointError, setPickupPointError] = useState<string | null>(null)

    const doorDeliveryPoint = useMemo(
        () => getDoorDeliveryPoint(doorDeliveryDraft),
        [doorDeliveryDraft],
    )
    const pickupPoint = useMemo(
        () => getPickupPoint(pickupPointDraft),
        [pickupPointDraft],
    )
    const searchOriginPoint = searchFocusPoint ?? doorDeliveryPoint ?? pickupPoint ?? userPoint
    const { clearResults, error, isLoading, results, runSearch } = useDeliveryGeoSearch(
        search,
        searchOriginPoint,
        searchEnabled,
    )
    const isSearchActive = isSearchFocused || searchPanelExpanded
    const hasVisibleSearchFeedback = isLoading || Boolean(error) || results.length > 0
    const shouldShowPickupFooterExtension =
        isPickupFooterExpanded &&
        !hasVisibleSearchFeedback &&
        Boolean(isResolvingPickupPoint || pickupPointDraft || pickupPointError)
    const shouldShowDoorFooterExtension =
        supportsDoorDelivery &&
        isDoorFooterExpanded &&
        !hasVisibleSearchFeedback &&
        Boolean(isResolvingDoorAddress || doorDeliveryDraft || selectionError)

    return {
        activeCountryCode,
        clearResults,
        doorDeliveryDraft,
        doorDeliveryPoint,
        error,
        hasVisibleSearchFeedback,
        isDoorFooterExpanded,
        isLoading,
        isResolvingDoorAddress,
        isResolvingPickupPoint,
        isSearchActive,
        isSearchFocused,
        pickupPoint,
        pickupPointDraft,
        pickupPointError,
        removedDeliveryPointKeys,
        results,
        runSearch,
        search,
        searchEnabled,
        searchFocusPoint,
        selectionError,
        setDoorDeliveryDraft,
        setIsDoorFooterExpanded,
        setIsPickupFooterExpanded,
        setIsResolvingDoorAddress,
        setIsResolvingPickupPoint,
        setIsSearchFocused,
        setPickupPointDraft,
        setPickupPointError,
        setRemovedDeliveryPointKeys,
        setSearch,
        setSearchEnabled,
        setSearchFocusPoint,
        setSelectionError,
        shouldShowDoorFooterExtension,
        shouldShowPickupFooterExtension,
        supportsDoorDelivery,
    }
}
