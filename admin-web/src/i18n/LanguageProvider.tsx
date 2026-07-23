import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react"
import type { Locale } from "../api/types"

const messages = {
  ru: {
    dashboard: "Главная",
    sales: "Продажи",
    orders: "Заказы",
    customers: "Клиенты",
    tasks: "Задачи",
    automation: "Автоматизация",
    catalog: "Каталог",
    products: "Товары",
    categories: "Категории",
    content: "Контент",
    reviews: "Отзывы",
    banners: "Баннеры",
    businessContent: "Юр. контент",
    marketing: "Маркетинг",
    communications: "Коммуникации",
    analytics: "Аналитика",
    integrations: "Интеграции",
    readiness: "Готовность",
    settings: "Настройки",
    staff: "Сотрудники",
    audit: "Журнал действий",
    search: "Найти заказ, клиента или товар",
    logout: "Выйти",
    environment: "Рабочая среда",
    loading: "Загрузка…",
    retry: "Повторить",
    save: "Сохранить",
    cancel: "Отмена",
    open: "Открыть",
    all: "Все",
    noData: "Нет данных",
    error: "Не удалось загрузить данные",
  },
  en: {
    dashboard: "Dashboard",
    sales: "Sales",
    orders: "Orders",
    customers: "Customers",
    tasks: "Tasks",
    automation: "Automation",
    catalog: "Catalog",
    products: "Products",
    categories: "Categories",
    content: "Content",
    reviews: "Reviews",
    banners: "Banners",
    businessContent: "Legal content",
    marketing: "Marketing",
    communications: "Communications",
    analytics: "Analytics",
    integrations: "Integrations",
    readiness: "Readiness",
    settings: "Settings",
    staff: "Staff",
    audit: "Audit log",
    search: "Find an order, customer or product",
    logout: "Sign out",
    environment: "Production workspace",
    loading: "Loading…",
    retry: "Retry",
    save: "Save",
    cancel: "Cancel",
    open: "Open",
    all: "All",
    noData: "No data",
    error: "Could not load data",
  },
} as const

type MessageKey = keyof typeof messages.ru
type LanguageContextValue = {
  locale: Locale
  setLocale: (locale: Locale) => void
  t: (key: MessageKey) => string
}

const LanguageContext = createContext<LanguageContextValue | null>(null)

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() =>
    window.localStorage.getItem("elixir-admin-locale") === "en" ? "en" : "ru",
  )
  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next)
    window.localStorage.setItem("elixir-admin-locale", next)
    document.documentElement.lang = next
  }, [])
  const value = useMemo<LanguageContextValue>(
    () => ({ locale, setLocale, t: (key) => messages[locale][key] }),
    [locale, setLocale],
  )
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useLanguage() {
  const context = useContext(LanguageContext)
  if (!context) throw new Error("useLanguage must be used inside LanguageProvider")
  return context
}
