import type {
    CreateOrderDraftPayload,
    DeliveryAddressRead,
    DeliveryRecipientRead,
    NewDeliveryAddressPayload,
    OrderDraftCheckoutOptionsRead,
    OrderDraftRead,
} from "@/services/api/order-drafts.types"
import type { AuthUser } from "@/services/auth/auth.types"
import type { BasketRead } from "@/types/basket"
import {
    calculateCdekDelivery,
    calculateYandexDelivery,
} from "@/services/api/delivery"
import type { CdekDeliveryCalculation } from "@/services/api/delivery.types"

import type {
    OrderDraftWithLegacyRecipientFields,
    RecipientFormErrors,
    RecipientFormState,
} from "@/screens/checkout/checkout-screen.types"

export function createEmptyRecipientForm(): RecipientFormState {
    return {
        firstName: "",
        lastName: "",
        phone: "",
        email: "",
    }
}

export function getRecipientFormFromRecipient(recipient: DeliveryRecipientRead | null | undefined) {
    if (!recipient) {
        return createEmptyRecipientForm()
    }

    return {
        firstName: recipient.name,
        lastName: recipient.surname,
        phone: recipient.phone,
        email: recipient.email,
    }
}

export function getDraftRecipient(orderDraft: OrderDraftRead | null | undefined): DeliveryRecipientRead | null {
    if (!orderDraft) {
        return null
    }

    const draftWithLegacyRecipient = orderDraft as OrderDraftWithLegacyRecipientFields
    if (draftWithLegacyRecipient.recipient) {
        return draftWithLegacyRecipient.recipient
    }

    const hasLegacyRecipientData = Boolean(
        draftWithLegacyRecipient.recipient_name?.trim()
        || draftWithLegacyRecipient.recipient_phone?.trim()
        || draftWithLegacyRecipient.recipient_email?.trim(),
    )
    if (!hasLegacyRecipientData) {
        return null
    }

    const normalizedName = draftWithLegacyRecipient.recipient_name?.trim() ?? ""
    const [name = "Покупатель", ...rest] = normalizedName ? normalizedName.split(/\s+/) : ["Покупатель"]

    return {
        id:
            draftWithLegacyRecipient.recipient_id && draftWithLegacyRecipient.recipient_id > 0
                ? draftWithLegacyRecipient.recipient_id
                : -orderDraft.id,
        user_id: orderDraft.user_id,
        name,
        surname: rest.join(" "),
        phone: draftWithLegacyRecipient.recipient_phone ?? "",
        email: draftWithLegacyRecipient.recipient_email ?? "",
        created_at: "",
        updated_at: "",
    }
}

export function getSelfRecipient(user: AuthUser | null | undefined): DeliveryRecipientRead | null {
    if (!user) {
        return null
    }

    return {
        id: 0,
        user_id: user.id,
        name: user.name,
        surname: user.surname,
        phone: user.phoneNumber ?? "",
        email: user.email,
        created_at: "",
        updated_at: "",
    }
}

export function normalizePhoneValue(value: string) {
    return value.replace(/[\s()-]/g, "")
}

export function isValidPhone(value: string) {
    const normalized = normalizePhoneValue(value.trim())
    return /^\+?\d{10,15}$/.test(normalized)
}

export function isValidEmail(value: string) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim())
}

export function hasRecipientErrors(errors: RecipientFormErrors) {
    return Object.values(errors).some(Boolean)
}

export function formatMoney(amount?: number | null, currency?: string | null) {
    if (amount === null || amount === undefined) {
        return null
    }

    if (currency) {
        try {
            return new Intl.NumberFormat("ru-RU", {
                style: "currency",
                currency,
                maximumFractionDigits: Number.isInteger(amount) ? 0 : 2,
            }).format(amount)
        } catch {
            return `${amount.toFixed(2)} ${currency}`
        }
    }

    return amount.toFixed(2)
}

export function parseDraftId(rawDraftId: string | string[] | undefined) {
    if (Array.isArray(rawDraftId)) {
        return parseDraftId(rawDraftId[0])
    }

    if (!rawDraftId) {
        return null
    }

    const draftId = Number(rawDraftId)
    return Number.isInteger(draftId) && draftId > 0 ? draftId : null
}

export function normalizeTextInputValue(value: string) {
    const normalized = value.trim()
    return normalized ? normalized : null
}

export function titleCaseWords(value: string | null | undefined) {
    const normalized = value?.trim()
    if (!normalized) {
        return ""
    }

    return normalized
        .toLocaleLowerCase("ru-RU")
        .replace(/\S+/g, (part) => part.charAt(0).toLocaleUpperCase("ru-RU") + part.slice(1))
}

export function getDraftUpdateErrorMessage(error: unknown, fallback: string) {
    if (error instanceof Error && error.message) {
        return error.message
    }

    return fallback
}

export function formatRecipientName(recipient: DeliveryRecipientRead | null | undefined) {
    if (!recipient) {
        return "Покупатель"
    }

    const fullName = [titleCaseWords(recipient.name), titleCaseWords(recipient.surname)].filter(Boolean).join(" ").trim()
    return fullName || "Покупатель"
}

export function buildAvailableRecipients(
    orderDraft: OrderDraftRead,
    checkoutOptions: OrderDraftCheckoutOptionsRead | null,
) {
    const recipients = checkoutOptions?.recipients?.length ? [...checkoutOptions.recipients] : []
    const currentRecipient = getDraftRecipient(orderDraft)

    if (currentRecipient && !recipients.some((option) => option.id === currentRecipient.id)) {
        recipients.unshift(currentRecipient)
    }

    return recipients
}

export function buildAvailableAddresses(orderDraft: OrderDraftRead, checkoutOptions: OrderDraftCheckoutOptionsRead | null) {
    const addresses = checkoutOptions?.addresses?.length ? [...checkoutOptions.addresses] : []
    const deliveryAddress = orderDraft.delivery_address

    if (deliveryAddress && !addresses.some((address) => address.id === deliveryAddress.id)) {
        addresses.unshift(deliveryAddress)
    }

    return addresses
}

export function basketMatchesDraft(basket: BasketRead | null | undefined, orderDraft: OrderDraftRead) {
    if (!basket || basket.items.length !== orderDraft.items.length) {
        return false
    }

    const basketItemQuantities = new Map(basket.items.map((item) => [item.variant_id, item.quantity]))
    if (basketItemQuantities.size !== basket.items.length) {
        return false
    }

    return orderDraft.items.every((item) => basketItemQuantities.get(item.variant_id) === item.quantity)
}

export function buildDraftPayloadFromOrderDraft(orderDraft: OrderDraftRead): CreateOrderDraftPayload {
    if (!orderDraft.delivery_address) {
        return {}
    }

    const deliveryAddress = orderDraft.delivery_address

    return {
        mode: deliveryAddress.mode,
        provider: deliveryAddress.provider,
        country_code: deliveryAddress.country_code,
        name: deliveryAddress.name,
        full_address: deliveryAddress.full_address,
        details: deliveryAddress.details,
        city: deliveryAddress.city,
        postal_code: deliveryAddress.postal_code,
        latitude: deliveryAddress.latitude,
        longitude: deliveryAddress.longitude,
        provider_reference: deliveryAddress.provider_reference,
        delivery_calculation: {
            delivery_sum: Number(orderDraft.delivery_total),
            period_min: orderDraft.delivery_period_min ?? 0,
            period_max: orderDraft.delivery_period_max ?? 0,
            currency: orderDraft.currency,
        },
    }
}

export function buildDeliveryCalculationPayload(
    deliveryCalculation: CdekDeliveryCalculation,
) {
    return {
        delivery_sum: deliveryCalculation.delivery_sum,
        period_min: deliveryCalculation.period_min,
        period_max: deliveryCalculation.period_max,
        currency: deliveryCalculation.currency,
    }
}

export async function calculateDeliveryForSavedAddress(
    deliveryAddress: DeliveryAddressRead,
): Promise<CdekDeliveryCalculation> {
    if (deliveryAddress.provider === "CDEK") {
        return calculateCdekDelivery({
            latitude: deliveryAddress.latitude,
            longitude: deliveryAddress.longitude,
            mode: deliveryAddress.mode === "pickup" ? "office" : "door",
            countryCode: deliveryAddress.country_code,
            postalCode: deliveryAddress.postal_code,
            address: deliveryAddress.full_address,
            city: deliveryAddress.city,
        })
    }

    if (deliveryAddress.provider === "YANDEX") {
        return calculateYandexDelivery(
            deliveryAddress.mode === "pickup"
                ? (deliveryAddress.provider_reference ?? deliveryAddress.full_address)
                : deliveryAddress.full_address,
        )
    }

    throw new Error(`Unsupported delivery provider: ${deliveryAddress.provider}`)
}

export function buildAddressUpdatePayloadWithCalculation(
    deliveryAddress: DeliveryAddressRead,
    deliveryCalculation: CdekDeliveryCalculation,
): NewDeliveryAddressPayload {
    return {
        mode: deliveryAddress.mode,
        provider: deliveryAddress.provider,
        country_code: deliveryAddress.country_code,
        name: deliveryAddress.name,
        full_address: deliveryAddress.full_address,
        details: deliveryAddress.details,
        city: deliveryAddress.city,
        postal_code: deliveryAddress.postal_code,
        latitude: deliveryAddress.latitude,
        longitude: deliveryAddress.longitude,
        provider_reference: deliveryAddress.provider_reference,
        delivery_calculation: buildDeliveryCalculationPayload(deliveryCalculation),
    }
}

export function formatSavedCartDraftName(date: Date) {
    const hours = String(date.getHours()).padStart(2, "0")
    const minutes = String(date.getMinutes()).padStart(2, "0")
    const day = String(date.getDate()).padStart(2, "0")
    const month = String(date.getMonth() + 1).padStart(2, "0")

    return `Корзина от ${hours}:${minutes} ${day}.${month}`
}
