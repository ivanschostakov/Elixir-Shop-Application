import * as SecureStore from "expo-secure-store"
import { Platform } from "react-native"

import { getBasketSnapshot, setBasketSnapshot } from "@/hooks/basket/basket-store"
import { quoteGuestBasket } from "@/services/api/guest"
import type { GuestBasketItemPayload } from "@/services/api/guest.types"
import type {
    DeliveryAddressRead,
    DeliveryCalculationPayload,
    DeliveryRecipientRead,
    NewDeliveryAddressPayload,
    NewRecipientPayload,
    UpdateOrderDraftPayload,
} from "@/services/api/order-drafts.types"
import type { BasketRead } from "@/types/basket"

const GUEST_CART_STORAGE_KEY = "elixirpeptide.guest.cart.v1"
const GUEST_BASKET_ID = -1
const GUEST_USER_ID = 0
const GUEST_RECIPIENT_ID = -1
const GUEST_DELIVERY_ADDRESS_ID = -1

let hasHydratedGuestCart = false
let guestCartItems: GuestBasketItemPayload[] = []

function normalizeGuestCartItems(items: GuestBasketItemPayload[]) {
    const quantitiesByVariantId = new Map<number, number>()

    for (const item of items) {
        if (!Number.isInteger(item.variant_id) || item.variant_id < 1 || !Number.isInteger(item.quantity) || item.quantity < 1) {
            continue
        }

        quantitiesByVariantId.set(
            item.variant_id,
            Math.min(100, (quantitiesByVariantId.get(item.variant_id) ?? 0) + item.quantity),
        )
    }

    return Array.from(quantitiesByVariantId.entries()).map(([variant_id, quantity]) => ({
        variant_id,
        quantity,
    }))
}

function parseGuestCartItems(rawValue: string | null) {
    if (!rawValue) {
        return []
    }

    try {
        const parsed = JSON.parse(rawValue)
        if (!Array.isArray(parsed)) {
            return []
        }

        return normalizeGuestCartItems(parsed as GuestBasketItemPayload[])
    } catch {
        return []
    }
}

async function hydrateGuestCartItems() {
    if (hasHydratedGuestCart) {
        return guestCartItems
    }

    if (Platform.OS === "web") {
        hasHydratedGuestCart = true
        return guestCartItems
    }

    try {
        guestCartItems = parseGuestCartItems(await SecureStore.getItemAsync(GUEST_CART_STORAGE_KEY))
    } catch {
        guestCartItems = []
    }

    hasHydratedGuestCart = true
    return guestCartItems
}

async function persistGuestCartItems(items: GuestBasketItemPayload[]) {
    guestCartItems = normalizeGuestCartItems(items)
    hasHydratedGuestCart = true

    if (Platform.OS === "web") {
        return
    }

    try {
        if (guestCartItems.length === 0) {
            await SecureStore.deleteItemAsync(GUEST_CART_STORAGE_KEY)
            return
        }

        await SecureStore.setItemAsync(GUEST_CART_STORAGE_KEY, JSON.stringify(guestCartItems))
    } catch {
        // Keep the in-memory cart usable even when secure storage is unavailable.
    }
}

function fixedMoney(value: number) {
    return value.toFixed(2)
}

function createEmptyGuestBasket(): BasketRead {
    const now = new Date().toISOString()

    return {
        id: GUEST_BASKET_ID,
        user_id: GUEST_USER_ID,
        items: [],
        delivery_address_id: null,
        recipient_id: null,
        delivery_address: null,
        recipient: null,
        items_count: 0,
        total_quantity: 0,
        total_amount: "0.00",
        delivery_total: "0.00",
        grand_total: "0.00",
        currency: "RUB",
        delivery_period_min: null,
        delivery_period_max: null,
        has_unavailable_items: false,
        created_at: now,
        updated_at: now,
    }
}

function isGuestBasket(basket: BasketRead | null | undefined) {
    return basket?.user_id === GUEST_USER_ID
}

function mergeGuestCheckout(prevBasket: BasketRead | null, nextBasket: BasketRead): BasketRead {
    if (!isGuestBasket(prevBasket) || !prevBasket?.items.length) {
        return nextBasket
    }

    const deliveryTotal = Number(prevBasket.delivery_total ?? 0)
    const grandTotal = Number(nextBasket.total_amount) + deliveryTotal

    return {
        ...nextBasket,
        delivery_address_id: prevBasket.delivery_address_id,
        recipient_id: prevBasket.recipient_id,
        delivery_address: prevBasket.delivery_address,
        recipient: prevBasket.recipient,
        delivery_total: fixedMoney(deliveryTotal),
        grand_total: fixedMoney(grandTotal),
        currency: prevBasket.currency || nextBasket.currency,
        delivery_period_min: prevBasket.delivery_period_min,
        delivery_period_max: prevBasket.delivery_period_max,
    }
}

function recalculateGuestBasketTotals(basket: BasketRead): BasketRead {
    const deliveryTotal = Number(basket.delivery_total ?? 0)
    const grandTotal = Number(basket.total_amount) + deliveryTotal

    return {
        ...basket,
        delivery_total: fixedMoney(deliveryTotal),
        grand_total: fixedMoney(grandTotal),
        updated_at: new Date().toISOString(),
    }
}

function buildGuestRecipient(payload: NewRecipientPayload): DeliveryRecipientRead {
    const now = new Date().toISOString()

    return {
        id: GUEST_RECIPIENT_ID,
        user_id: GUEST_USER_ID,
        name: payload.name,
        surname: payload.surname,
        phone: payload.phone,
        email: payload.email,
        created_at: now,
        updated_at: now,
    }
}

function requireDeliveryCalculation(
    payload: NewDeliveryAddressPayload,
    currentBasket: BasketRead,
): DeliveryCalculationPayload {
    if (payload.delivery_calculation) {
        return payload.delivery_calculation
    }

    if (currentBasket.delivery_total && Number(currentBasket.delivery_total) >= 0) {
        return {
            delivery_sum: Number(currentBasket.delivery_total),
            period_min: currentBasket.delivery_period_min ?? 0,
            period_max: currentBasket.delivery_period_max ?? 0,
            currency: currentBasket.currency,
        }
    }

    throw new Error("Delivery calculation is required")
}

function buildGuestDeliveryAddress(
    payload: NewDeliveryAddressPayload,
    currentBasket: BasketRead,
): { address: DeliveryAddressRead; calculation: DeliveryCalculationPayload } {
    const now = new Date().toISOString()
    const calculation = requireDeliveryCalculation(payload, currentBasket)

    return {
        address: {
            id: GUEST_DELIVERY_ADDRESS_ID,
            user_id: GUEST_USER_ID,
            mode: payload.mode ?? "door",
            provider: payload.provider ?? "CDEK",
            country_code: payload.country_code ?? "RU",
            name: payload.name ?? payload.full_address,
            full_address: payload.full_address,
            details: payload.details ?? null,
            city: payload.city ?? null,
            postal_code: payload.postal_code ?? null,
            latitude: payload.latitude ?? 0,
            longitude: payload.longitude ?? 0,
            provider_reference: payload.provider_reference ?? null,
            created_at: now,
            updated_at: now,
        },
        calculation,
    }
}

export async function getGuestCartItems() {
    return hydrateGuestCartItems()
}

export async function getGuestBasket(): Promise<BasketRead> {
    const items = await hydrateGuestCartItems()
    const quotedBasket = items.length
        ? await quoteGuestBasket({ items })
        : createEmptyGuestBasket()

    return mergeGuestCheckout(getBasketSnapshot(), quotedBasket)
}

async function saveGuestItemsAndQuote(nextItems: GuestBasketItemPayload[]) {
    await persistGuestCartItems(nextItems)
    const nextBasket = await getGuestBasket()
    setBasketSnapshot(nextBasket)
    return nextBasket
}

export async function addGuestCartItem(variantId: number, quantity: number) {
    const items = await hydrateGuestCartItems()
    return saveGuestItemsAndQuote([
        ...items,
        {
            variant_id: variantId,
            quantity,
        },
    ])
}

export async function updateGuestCartItemQuantity(itemId: number, quantity: number) {
    const items = await hydrateGuestCartItems()
    return saveGuestItemsAndQuote(
        items.map((item) => (
            item.variant_id === itemId
                ? { ...item, quantity }
                : item
        )),
    )
}

export async function removeGuestCartItem(itemId: number) {
    const items = await hydrateGuestCartItems()
    return saveGuestItemsAndQuote(items.filter((item) => item.variant_id !== itemId))
}

export async function clearGuestCart({ updateSnapshot = true }: { updateSnapshot?: boolean } = {}) {
    await persistGuestCartItems([])
    const emptyBasket = createEmptyGuestBasket()

    if (updateSnapshot) {
        setBasketSnapshot(emptyBasket)
    }

    return emptyBasket
}

export async function updateGuestBasketCheckout(payload: UpdateOrderDraftPayload): Promise<BasketRead> {
    const currentBasket = getBasketSnapshot() ?? await getGuestBasket()
    let nextBasket: BasketRead = {
        ...currentBasket,
        id: GUEST_BASKET_ID,
        user_id: GUEST_USER_ID,
    }

    if ("new_recipient" in payload && payload.new_recipient) {
        const recipient = buildGuestRecipient(payload.new_recipient)
        nextBasket = {
            ...nextBasket,
            recipient_id: recipient.id,
            recipient,
        }
    } else if (payload.recipient_id === null || payload.new_recipient === null) {
        nextBasket = {
            ...nextBasket,
            recipient_id: null,
            recipient: null,
        }
    }

    if ("new_delivery_address" in payload && payload.new_delivery_address) {
        const { address, calculation } = buildGuestDeliveryAddress(payload.new_delivery_address, nextBasket)
        nextBasket = {
            ...nextBasket,
            delivery_address_id: address.id,
            delivery_address: address,
            delivery_total: fixedMoney(Number(calculation.delivery_sum)),
            delivery_period_min: calculation.period_min,
            delivery_period_max: calculation.period_max,
            currency: calculation.currency || nextBasket.currency,
        }
    } else if (payload.new_delivery_address === null) {
        nextBasket = {
            ...nextBasket,
            delivery_address_id: null,
            delivery_address: null,
            delivery_total: "0.00",
            delivery_period_min: null,
            delivery_period_max: null,
        }
    }

    nextBasket = recalculateGuestBasketTotals(nextBasket)
    setBasketSnapshot(nextBasket)
    return nextBasket
}
