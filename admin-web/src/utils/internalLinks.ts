import type { Locale } from "../api/types"

export type InternalAppLinkGuideEntry = {
  key: string
  page: { ru: string; en: string }
  path: string
  parameters: { ru: string; en: string }
  example: string
  access: "public" | "account" | "context"
  note?: { ru: string; en: string }
}

export const INTERNAL_APP_LINK_GUIDE: InternalAppLinkGuideEntry[] = [
  {
    key: "home",
    page: { ru: "Главная", en: "Home" },
    path: "/",
    parameters: { ru: "Нет", en: "None" },
    example: "/",
    access: "public",
  },
  {
    key: "catalog-products",
    page: { ru: "Каталог товаров", en: "Product catalog" },
    path: "/discover",
    parameters: { ru: "tab=products", en: "tab=products" },
    example: "/discover?tab=products",
    access: "public",
  },
  {
    key: "catalog-articles",
    page: { ru: "Статьи", en: "Articles" },
    path: "/discover",
    parameters: { ru: "tab=articles", en: "tab=articles" },
    example: "/discover?tab=articles",
    access: "public",
  },
  {
    key: "catalog-search",
    page: { ru: "Поиск по каталогу", en: "Catalog search" },
    path: "/discover",
    parameters: { ru: "q=поисковый запрос; tab=products", en: "q=search query; tab=products" },
    example: "/discover?tab=products&q=ghk-cu",
    access: "public",
    note: {
      ru: "Пробелы и специальные символы нужно URL-кодировать.",
      en: "Spaces and special characters must be URL-encoded.",
    },
  },
  {
    key: "catalog-category",
    page: { ru: "Категория товаров", en: "Product category" },
    path: "/discover",
    parameters: { ru: "categoryId=ID категории; resetCategory=1 сбрасывает фильтр", en: "categoryId=category ID; resetCategory=1 clears the filter" },
    example: "/discover?tab=products&categoryId=12",
    access: "public",
  },
  {
    key: "product",
    page: { ru: "Карточка товара", en: "Product details" },
    path: "/products/{productId}",
    parameters: { ru: "productId - числовой ID товара", en: "productId - numeric product ID" },
    example: "/products/123",
    access: "public",
  },
  {
    key: "basket",
    page: { ru: "Корзина", en: "Basket" },
    path: "/basket",
    parameters: { ru: "Нет", en: "None" },
    example: "/basket",
    access: "public",
  },
  {
    key: "favorites",
    page: { ru: "Избранное", en: "Favorites" },
    path: "/favorites",
    parameters: { ru: "tab=products или tab=articles", en: "tab=products or tab=articles" },
    example: "/favorites?tab=products",
    access: "account",
  },
  {
    key: "chat-ai",
    page: { ru: "AI-чат", en: "AI chat" },
    path: "/chat",
    parameters: { ru: "mode=ai", en: "mode=ai" },
    example: "/chat?mode=ai",
    access: "account",
  },
  {
    key: "chat-community",
    page: { ru: "Чат сообщества", en: "Community chat" },
    path: "/chat",
    parameters: { ru: "mode=community; topicId=ID темы (необязательно)", en: "mode=community; topicId=topic ID (optional)" },
    example: "/chat?mode=community",
    access: "account",
  },
  {
    key: "chat-support",
    page: { ru: "Поддержка", en: "Support" },
    path: "/chat",
    parameters: { ru: "mode=support; conversationId=ID обращения (необязательно)", en: "mode=support; conversationId=conversation ID (optional)" },
    example: "/chat?mode=support",
    access: "account",
    note: {
      ru: "ID обращения должен принадлежать получателю ссылки.",
      en: "The conversation ID must belong to the link recipient.",
    },
  },
  {
    key: "profile",
    page: { ru: "Профиль", en: "Profile" },
    path: "/profile",
    parameters: { ru: "Нет", en: "None" },
    example: "/profile",
    access: "account",
  },
  {
    key: "personal-data",
    page: { ru: "Персональные данные", en: "Personal data" },
    path: "/personal-data",
    parameters: { ru: "Нет", en: "None" },
    example: "/personal-data",
    access: "account",
  },
  {
    key: "profile-drafts",
    page: { ru: "Черновики заказов", en: "Order drafts" },
    path: "/profile-drafts",
    parameters: { ru: "Нет", en: "None" },
    example: "/profile-drafts",
    access: "account",
  },
  {
    key: "profile-history",
    page: { ru: "История заказов", en: "Order history" },
    path: "/profile-history",
    parameters: { ru: "Нет", en: "None" },
    example: "/profile-history",
    access: "account",
  },
  {
    key: "checkout",
    page: { ru: "Оформление заказа", en: "Checkout" },
    path: "/checkout",
    parameters: { ru: "draftId=ID черновика; code=промокод", en: "draftId=draft ID; code=promo code" },
    example: "/checkout",
    access: "context",
    note: {
      ru: "Без draftId откроется оформление текущей корзины.",
      en: "Without draftId, checkout opens for the current basket.",
    },
  },
  {
    key: "delivery",
    page: { ru: "Выбор доставки", en: "Delivery selection" },
    path: "/delivery",
    parameters: { ru: "draftId=ID черновика; syncBasket=1", en: "draftId=draft ID; syncBasket=1" },
    example: "/delivery",
    access: "context",
    note: {
      ru: "Используйте только когда у клиента уже есть корзина или черновик.",
      en: "Use only when the customer already has a basket or draft.",
    },
  },
  {
    key: "payment",
    page: { ru: "Оплата", en: "Payment" },
    path: "/payment",
    parameters: { ru: "orderId или draftId; paymentMethod=sbp|later; code=промокод", en: "orderId or draftId; paymentMethod=sbp|later; code=promo code" },
    example: "/payment?orderId=123",
    access: "context",
    note: {
      ru: "Не используйте статический orderId в массовой кампании.",
      en: "Do not use a static orderId in a mass campaign.",
    },
  },
  {
    key: "contacts",
    page: { ru: "Контакты", en: "Contacts" },
    path: "/contacts",
    parameters: { ru: "Нет", en: "None" },
    example: "/contacts",
    access: "public",
  },
  {
    key: "requisites",
    page: { ru: "Реквизиты", en: "Legal details" },
    path: "/requisites",
    parameters: { ru: "Нет", en: "None" },
    example: "/requisites",
    access: "public",
  },
  {
    key: "public-offer",
    page: { ru: "Публичная оферта", en: "Public offer" },
    path: "/public-offer",
    parameters: { ru: "Нет", en: "None" },
    example: "/public-offer",
    access: "public",
  },
]

const EXACT_INTERNAL_PATHS = new Set([
  "/",
  "/discover",
  "/chat",
  "/basket",
  "/checkout",
  "/delivery",
  "/favorites",
  "/payment",
  "/profile",
  "/personal-data",
  "/profile-drafts",
  "/profile-history",
  "/contacts",
  "/requisites",
  "/public-offer",
])

export function internalAppLinkError(value: unknown, locale: Locale): string | null {
  if (value === null || value === undefined || value === "") return null
  const link = String(value).trim()
  const copy = locale === "ru"
    ? {
      prefix: "Внутренняя ссылка должна начинаться с одного символа /",
      unsupported: "Такой страницы нет в справочнике внутренних ссылок",
      product: "В ссылке на товар должен быть числовой ID: /products/123",
    }
    : {
      prefix: "An internal link must begin with a single /",
      unsupported: "This page is not in the internal link guide",
      product: "A product link must contain a numeric ID: /products/123",
    }
  if (!link.startsWith("/") || link.startsWith("//")) return copy.prefix

  let parsed: URL
  try {
    parsed = new URL(link, "https://elixir.local")
  } catch {
    return copy.unsupported
  }
  const path = parsed.pathname.replace(/\/+$/, "") || "/"
  if (path.startsWith("/products/")) {
    return /^\d+$/.test(path.slice("/products/".length)) ? null : copy.product
  }
  return EXACT_INTERNAL_PATHS.has(path) ? null : copy.unsupported
}

export function internalAppLinkValidator(locale: Locale) {
  return async (_rule: unknown, value: unknown) => {
    const error = internalAppLinkError(value, locale)
    if (error) throw new Error(error)
  }
}
