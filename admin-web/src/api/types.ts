export type Locale = "ru" | "en"

export type AdminPrincipal = {
  user: {
    id: number
    email: string | null
    name: string
    surname: string
    locale: Locale
  }
  roles: string[]
  permissions: string[]
}

export type AdminAuthResponse = {
  access_token: string
  token_type: "bearer"
  expires_in: number
  principal: AdminPrincipal
}

export type AdminChallenge = {
  status: "mfa_required" | "mfa_setup_required"
  challenge_token: string
  expires_in: number
}

export type Page<T> = {
  items: T[]
  total: number
  limit: number
  offset: number
}

export type Dashboard = {
  metrics: {
    revenue: string
    paid_orders: number
    average_order_value: string
    new_customers: number
    failed_payments: number
    pending_reviews: number
    low_stock_variants: number
    abandoned_baskets: number
    integration_errors: number
  }
  revenue_trend: Array<{ day: string; revenue: string; orders: number }>
}

export type OrderStatusCode =
  | "created"
  | "invoice_sent"
  | "paid"
  | "waiting_response"
  | "packaged"
  | "sent"
  | "delivered"
  | "canceled"
  | "completed"
  | "refund_declined"

export type CustomerCompact = {
  id: number
  name: string
  surname: string
  email: string | null
  phone_number: string | null
}

export type OrderListItem = {
  id: number
  order_code: string
  status: string
  status_code: OrderStatusCode
  customer: CustomerCompact
  items_count: number
  total_quantity: number
  grand_total: string
  currency: string
  payment_method: string | null
  payment_status: string
  delivery_service: string
  is_paid: boolean
  is_canceled: boolean
  amocrm_lead_id: number | null
  created_at: string
  updated_at: string
}

export type OrderDetail = OrderListItem & {
  basket_subtotal: string
  delivery_total: string
  comment: string | null
  delivery_string: string | null
  delivery_period_min: number | null
  delivery_period_max: number | null
  payment_provider: string | null
  payment_invoice_id: string | null
  payment_paid_at: string | null
  payment_error: string | null
  delivery_created_at: string | null
  delivery_provider_ref: string | null
  yandex_request_id: string | null
  moysklad_customerorder_id: string | null
  moysklad_invoiceout_id: string | null
  recipient: Record<string, unknown>
  address: Record<string, unknown>
  items: Array<{
    id: number
    product_id: number
    variant_id: number
    product_name: string
    product_sku: string
    variant_name: string
    variant_sku: string | null
    quantity: number
    unit_price: string
    line_total: string
  }>
  benefits: Record<string, unknown>
}

export type CustomerListItem = CustomerCompact & {
  is_active: boolean
  is_verified: boolean
  telegram_username: string | null
  orders_count: number
  paid_total: string
  last_order_at: string | null
  last_active_at: string | null
  created_at: string
  updated_at: string
}

export type CustomerDetail = CustomerListItem & {
  contact_id: number | null
  moysklad_counterparty_id: string | null
  promo_code: string | null
  basket_items: number
  basket_total: string
  favourites_count: number
  push_tokens_count: number
  referral_discount_base_total: string
  referral_discount_percent: string
  total_product_views: number
  total_cart_quantity: number
  notes: Array<{ id: number; body: string; author_name: string; created_at: string; updated_at: string }>
}

export type Product = {
  id: number
  system_id: string
  sku: string
  name: string
  description: string | null
  usage: string | null
  expiration: string | null
  in_stock: boolean
  archived: boolean
  priority: number
  image_url: string
  category_ids: number[]
  variants: Array<{
    id: number
    system_id: string
    sku: string | null
    name: string
    stock: number
    price: string
    archived: boolean
  }>
  updated_at: string
}

export type Category = {
  id: number
  name: string
  description: string | null
  archived: boolean
  created_at: string
  updated_at: string
}

export type Review = {
  id: number
  product_id: number
  product_name: string
  user_id: number | null
  author_name: string
  author_email: string | null
  value: number
  text: string | null
  answer: string | null
  status: "pending" | "published" | "rejected"
  attachments: string[]
  created_at: string
  updated_at: string
}

export type Banner = {
  id: number
  image_path: string
  inner_link: string | null
  outer_link: string | null
  priority: number
  archived: boolean
  created_at: string
  updated_at: string
}

export type IntegrationStatus = {
  provider: string
  label: string
  configured: boolean
  status: "healthy" | "warning" | "error" | "disabled"
  last_run_at: string | null
  last_run_status: string | null
  last_error: string | null
}

export type IntegrationRun = {
  id: number
  provider: string
  operation: string
  status: string
  attempts: number
  counters_json: Record<string, unknown>
  error: string | null
  started_at: string
  finished_at: string | null
}

export type Role = {
  id: number
  code: string
  name_ru: string
  name_en: string
  permissions: string[]
}

export type Staff = {
  user_id: number
  email: string | null
  name: string
  surname: string
  is_active: boolean
  mfa_enabled: boolean
  last_login_at: string | null
  role_codes: string[]
}

export type AuditLog = {
  id: number
  actor_name: string
  action: string
  entity_type: string
  entity_id: string | null
  before_json: Record<string, unknown> | null
  after_json: Record<string, unknown> | null
  context_json: Record<string, unknown>
  ip_address: string | null
  request_id: string | null
  created_at: string
}

export type SearchResult = {
  type: "order" | "customer" | "product"
  id: number
  title: string
  subtitle: string
  path: string
}

export type ReferralProfile = {
  id: number
  user_id: number
  total_purchases: string
  referral_discount_base_total: string
  current_discount_percent: string
  created_at: string
  updated_at: string
}
