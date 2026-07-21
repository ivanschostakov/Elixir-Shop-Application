import dayjs from "dayjs"
import type { Locale, OrderStatusCode } from "../api/types"

export const statusColors: Record<OrderStatusCode, string> = {
  created: "default",
  invoice_sent: "processing",
  paid: "green",
  waiting_response: "orange",
  packaged: "cyan",
  sent: "blue",
  delivered: "geekblue",
  canceled: "red",
  completed: "success",
  refund_declined: "volcano",
}

const statusLabels: Record<Locale, Record<OrderStatusCode, string>> = {
  ru: {
    created: "Создан",
    invoice_sent: "Счёт отправлен",
    paid: "Оплачен",
    waiting_response: "Ожидание ответа",
    packaged: "Укомплектован",
    sent: "Отправлен",
    delivered: "Доставлен",
    canceled: "Отменён",
    completed: "Завершён",
    refund_declined: "Возврат / отказ",
  },
  en: {
    created: "Created",
    invoice_sent: "Invoice sent",
    paid: "Paid",
    waiting_response: "Waiting for response",
    packaged: "Packaged",
    sent: "Sent",
    delivered: "Delivered",
    canceled: "Canceled",
    completed: "Completed",
    refund_declined: "Refund / declined",
  },
}

export function statusLabel(status: OrderStatusCode, locale: Locale) {
  return statusLabels[locale][status]
}

export function money(value: string | number, currency = "RUB", locale: Locale = "ru") {
  return new Intl.NumberFormat(locale === "ru" ? "ru-RU" : "en-US", { style: "currency", currency, maximumFractionDigits: 2 }).format(Number(value || 0))
}

export function dateTime(value: string | null | undefined, locale: Locale = "ru") {
  if (!value) return "—"
  return dayjs(value).format(locale === "ru" ? "DD.MM.YYYY, HH:mm" : "MMM D, YYYY, HH:mm")
}
