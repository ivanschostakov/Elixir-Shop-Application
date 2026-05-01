import type { TranslationKey } from "@/i18n/translations"
import type { GetOrdersQuery, OrderHistoryBucket, OrderStatusCode } from "@/services/api/orders.types"

export type ProfileHistoryFilters = {
    statusCode: OrderStatusCode | null
    createdFrom: string | null
    createdTo: string | null
}

export const ACTIVE_ORDER_STATUS_CODES: readonly OrderStatusCode[] = [
    "created",
    "invoice_sent",
    "paid",
    "waiting_response",
    "packaged",
    "sent",
]

export const COMPLETED_ORDER_STATUS_CODES: readonly OrderStatusCode[] = [
    "delivered",
    "completed",
    "canceled",
    "refund_declined",
]

export const ORDER_STATUS_LABEL_KEYS: Record<OrderStatusCode, TranslationKey> = {
    created: "profile.history.status.created",
    invoice_sent: "profile.history.status.invoice_sent",
    paid: "profile.history.status.paid",
    waiting_response: "profile.history.status.waiting_response",
    packaged: "profile.history.status.packaged",
    sent: "profile.history.status.sent",
    delivered: "profile.history.status.delivered",
    canceled: "profile.history.status.canceled",
    completed: "profile.history.status.completed",
    refund_declined: "profile.history.status.refund_declined",
}

export const ORDER_STATUS_MESSAGE_KEYS: Record<OrderStatusCode, TranslationKey> = {
    created: "profile.history.statusMessage.created",
    invoice_sent: "profile.history.statusMessage.invoice_sent",
    paid: "profile.history.statusMessage.paid",
    waiting_response: "profile.history.statusMessage.waiting_response",
    packaged: "profile.history.statusMessage.packaged",
    sent: "profile.history.statusMessage.sent",
    delivered: "profile.history.statusMessage.delivered",
    canceled: "profile.history.statusMessage.canceled",
    completed: "profile.history.statusMessage.completed",
    refund_declined: "profile.history.statusMessage.refund_declined",
}

type CalendarDayParts = {
    day: number
    month: number
    year: number
}

function parseCalendarDate(value: string | null): CalendarDayParts | null {
    if (!value) {
        return null
    }

    const [yearValue, monthValue, dayValue] = value.split("-")
    const year = Number(yearValue)
    const month = Number(monthValue)
    const day = Number(dayValue)

    if (!Number.isInteger(year) || !Number.isInteger(month) || !Number.isInteger(day)) {
        return null
    }

    const date = new Date(year, month - 1, day)
    if (
        date.getFullYear() !== year
        || date.getMonth() !== month - 1
        || date.getDate() !== day
    ) {
        return null
    }

    return {
        day,
        month,
        year,
    }
}

function toDisplayDate(value: string) {
    const calendarDatePattern = /^\d{4}-\d{2}-\d{2}$/
    if (calendarDatePattern.test(value)) {
        const parsed = parseCalendarDate(value)
        if (parsed) {
            return new Date(parsed.year, parsed.month - 1, parsed.day)
        }
    }

    return new Date(value)
}

function toCalendarDateString(date: Date) {
    const pad = (value: number) => String(value).padStart(2, "0")

    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

function toLocalDate(value: string) {
    const parsed = parseCalendarDate(value)
    if (!parsed) {
        return null
    }

    return new Date(parsed.year, parsed.month - 1, parsed.day)
}

function addDays(value: string, amount: number) {
    const date = toLocalDate(value)
    if (!date) {
        return value
    }

    date.setDate(date.getDate() + amount)
    return toCalendarDateString(date)
}

function toOffsetIsoString(date: Date) {
    const pad = (value: number, length = 2) => String(Math.abs(value)).padStart(length, "0")
    const offsetMinutes = -date.getTimezoneOffset()
    const offsetSign = offsetMinutes >= 0 ? "+" : "-"
    const offsetHours = Math.floor(Math.abs(offsetMinutes) / 60)
    const offsetRemainderMinutes = Math.abs(offsetMinutes) % 60

    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
        + `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
        + `${offsetSign}${pad(offsetHours)}:${pad(offsetRemainderMinutes)}`
}

export function getStatusCodesForBucket(bucket: OrderHistoryBucket): readonly OrderStatusCode[] {
    if (bucket === "completed") {
        return COMPLETED_ORDER_STATUS_CODES
    }

    return ACTIVE_ORDER_STATUS_CODES
}

export function buildDateQueryValue(value: string | null, endOfDay = false) {
    const parsed = parseCalendarDate(value)
    if (!parsed) {
        return null
    }

    const date = new Date(
        parsed.year,
        parsed.month - 1,
        parsed.day,
        endOfDay ? 23 : 0,
        endOfDay ? 59 : 0,
        endOfDay ? 59 : 0,
        endOfDay ? 999 : 0,
    )

    return toOffsetIsoString(date)
}

export function buildOrderHistoryQuery(
    bucket: OrderHistoryBucket,
    filters: ProfileHistoryFilters,
    limit: number,
    offset: number,
): GetOrdersQuery {
    return {
        limit,
        offset,
        history_bucket: bucket,
        status_code: filters.statusCode,
        created_from: buildDateQueryValue(filters.createdFrom),
        created_to: buildDateQueryValue(filters.createdTo, true),
    }
}

export function formatHistoryDate(value: string) {
    try {
        return new Intl.DateTimeFormat("ru-RU", {
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
        }).format(toDisplayDate(value))
    } catch {
        return value
    }
}

export function formatHistoryDateWithoutYear(value: string) {
    try {
        return new Intl.DateTimeFormat("ru-RU", {
            day: "2-digit",
            month: "2-digit",
        }).format(toDisplayDate(value))
    } catch {
        return value
    }
}

export function formatDateRangeTriggerValue(
    createdFrom: string | null,
    createdTo: string | null,
    emptyLabel: string,
) {
    if (!createdFrom) {
        return emptyLabel
    }

    if (!createdTo || createdFrom === createdTo) {
        return formatHistoryDateWithoutYear(createdFrom)
    }

    return `${formatHistoryDateWithoutYear(createdFrom)} - ${formatHistoryDateWithoutYear(createdTo)}`
}

export function buildDateRangeSelection(
    current: Pick<ProfileHistoryFilters, "createdFrom" | "createdTo">,
    pressedDate: string,
) {
    if (!current.createdFrom || (current.createdFrom && current.createdTo)) {
        return {
            createdFrom: pressedDate,
            createdTo: null,
        }
    }

    if (pressedDate === current.createdFrom) {
        return {
            createdFrom: pressedDate,
            createdTo: pressedDate,
        }
    }

    if (pressedDate < current.createdFrom) {
        return {
            createdFrom: pressedDate,
            createdTo: current.createdFrom,
        }
    }

    return {
        createdFrom: current.createdFrom,
        createdTo: pressedDate,
    }
}

export function buildMarkedDateRange(
    createdFrom: string | null,
    createdTo: string | null,
    palette: {
        rangeColor: string
        rangeTextColor: string
        selectedColor: string
        selectedTextColor: string
    },
) {
    if (!createdFrom) {
        return {}
    }

    const rangeEnd = createdTo ?? createdFrom
    const markedDates: Record<string, Record<string, boolean | string>> = {}
    let cursor = createdFrom

    while (cursor <= rangeEnd) {
        const isStart = cursor === createdFrom
        const isEnd = cursor === rangeEnd

        markedDates[cursor] = {
            color: isStart || isEnd ? palette.selectedColor : palette.rangeColor,
            endingDay: isEnd,
            startingDay: isStart,
            textColor: isStart || isEnd ? palette.selectedTextColor : palette.rangeTextColor,
        }

        if (cursor === rangeEnd) {
            break
        }

        cursor = addDays(cursor, 1)
    }

    return markedDates
}

export function getAppliedDateRange(range: Pick<ProfileHistoryFilters, "createdFrom" | "createdTo">) {
    if (!range.createdFrom) {
        return {
            createdFrom: null,
            createdTo: null,
        }
    }

    return {
        createdFrom: range.createdFrom,
        createdTo: range.createdTo ?? range.createdFrom,
    }
}

export function getTodayCalendarDate() {
    return toCalendarDateString(new Date())
}
