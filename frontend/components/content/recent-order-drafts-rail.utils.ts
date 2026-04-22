import type { ViewStyle } from "react-native"

import type { OrderDraftRead } from "@/services/api/order-drafts.types"

import { DRAFT_DESCRIPTION_VISIBLE_ITEMS } from "@/components/content/recent-order-drafts-rail.constants"

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

export function getPositionsLabel(count: number) {
    const mod10 = count % 10
    const mod100 = count % 100

    if (mod10 === 1 && mod100 !== 11) {
        return "позиция"
    }

    if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) {
        return "позиции"
    }

    return "позиций"
}

export function getDraftDescription(draft: OrderDraftRead) {
    const visibleItems = draft.items.slice(0, DRAFT_DESCRIPTION_VISIBLE_ITEMS)
    const hiddenItemsCount = Math.max(draft.items.length - visibleItems.length, 0)
    const lines = visibleItems.map((item) => `${item.product_name} ×${item.quantity}`)

    if (hiddenItemsCount > 0) {
        lines.push(`И еще ${hiddenItemsCount} ${getPositionsLabel(hiddenItemsCount)}`)
    }

    return lines.join("\n")
}

export function getModeBadgeStyle(count: number, index: number): ViewStyle {
    if (count <= 1) {
        return {
            borderRadius: 24,
            bottom: 0,
            left: 0,
            right: 0,
            top: 0,
        }
    }

    if (count === 2) {
        return index === 0
            ? {
                  borderBottomLeftRadius: 24,
                  borderTopLeftRadius: 24,
                  bottom: 0,
                  left: 0,
                  top: 0,
                  width: "49%",
              }
            : {
                  borderBottomRightRadius: 24,
                  borderTopRightRadius: 24,
                  bottom: 0,
                  right: 0,
                  top: 0,
                  width: "49%",
              }
    }

    if (count === 3) {
        if (index === 0) {
            return {
                borderBottomLeftRadius: 24,
                borderTopLeftRadius: 24,
                bottom: 0,
                left: 0,
                top: 0,
                width: "60%",
            }
        }

        if (index === 1) {
            return {
                borderTopRightRadius: 24,
                height: "48%",
                right: 0,
                top: 0,
                width: "38%",
            }
        }

        return {
            borderBottomRightRadius: 24,
            bottom: 0,
            height: "48%",
            right: 0,
            width: "38%",
        }
    }

    if (index === 0) {
        return {
            borderTopLeftRadius: 24,
            height: "60%",
            left: 0,
            top: 0,
            width: "58%",
        }
    }

    if (index === 1) {
        return {
            borderTopRightRadius: 24,
            height: "32%",
            right: 0,
            top: 0,
            width: "40%",
        }
    }

    if (index === 2) {
        return {
            height: "26%",
            right: 0,
            top: "34%",
            width: "40%",
        }
    }

    return {
        borderBottomLeftRadius: 24,
        borderBottomRightRadius: 24,
        bottom: 0,
        height: "38%",
        left: 0,
        width: "100%",
    }
}

export function normalizeDraftText(value: string) {
    const normalized = value.trim()
    return normalized ? normalized : null
}

export function getDraftUpdateErrorMessage(error: unknown, fallback: string) {
    if (error instanceof Error && error.message) {
        return error.message
    }

    return fallback
}
