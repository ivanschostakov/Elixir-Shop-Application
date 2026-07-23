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
    overdue_tasks: number
    sla_breached_tasks: number
    sla_compliance_percent: string
  }
  revenue_trend: Array<{ day: string; revenue: string; orders: number }>
}

export type AnalyticsSnapshot = {
  days: number
  generated_at: string
  sales: {
    summary: {
      revenue: string
      paid_orders: number
      units_sold: number
      average_order_value: string
      customers: number
      repeat_customers: number
      repeat_rate: string
    }
    trend: Array<{ date: string; revenue: string; orders: number }>
    payment_statuses: Array<{ status: string; count: number }>
  }
  customers: {
    summary: {
      total_customers: number
      new_customers: number
      active_customers: number
      inactive_customers: number
      abandoned_carts: number
      activation_rate: string
    }
    top_customers: Array<{ user_id: number; name: string; email: string | null; orders: number; ltv: string }>
    segments: Array<{ name: string; count: number }>
    devices: {
      platforms: Array<{ platform: string; customers: number }>
      app_versions: Array<{ platform: string; app_version: string; customers: number }>
      push_permissions: Array<{ permission: string; customers: number }>
    }
    events: Array<{ event_name: string; events: number; customers: number }>
  }
  products: {
    summary: {
      active_products: number
      in_stock_products: number
      stock_coverage_rate: string
      low_stock_products: number
    }
    top_products: Array<{ product_id: number; name: string; sku: string; quantity: number; revenue: string }>
    low_stock: Array<{ product_id: number; name: string; sku: string; stock: number }>
  }
  discounts: {
    summary: {
      total_discount: string
      applications: number
      referral_profiles: number
      active_referrals: number
      active_referral_rate: string
    }
    sources: Array<{ source: string; applications: number; discount_amount: string }>
  }
  marketing: {
    summary: {
      campaigns: number
      audience: number
      sent: number
      failed: number
      clicked: number
      delivery_rate: string
      click_rate: string
      failure_rate: string
    }
    campaigns: Array<{ campaign_id: number; name: string; status: string; goal: string | null; audience: number; sent: number; failed: number; clicked: number; delivery_rate: string; click_rate: string; created_at: string }>
  }
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
  marketing_profile: {
    lifecycle_stage: string
    lead_score: number
    engagement_score: number
    first_seen_at: string | null
    last_seen_at: string | null
    last_event_name: string | null
    last_platform: string | null
    last_app_version: string | null
    push_permission: string
    preferred_language: string | null
    timezone: string | null
    sessions_count: number
    total_events: number
    product_views: number
    category_views: number
    searches_count: number
    banner_clicks: number
    push_opens: number
    push_clicks: number
    cart_adds: number
    cart_removes: number
    checkout_started: number
    checkout_failed: number
    orders_created: number
    orders_paid: number
    last_purchase_at: string | null
    updated_at: string
  } | null
  devices: Array<{
    id: number
    installation_id: string
    platform: string
    app_version: string | null
    app_build: string | null
    os_version: string | null
    device_model: string | null
    language: string | null
    timezone: string | null
    push_permission: string
    install_source: string | null
    first_seen_at: string
    last_seen_at: string
    sessions_count: number
    is_active: boolean
  }>
  recent_events: Array<{
    id: number
    event_id: string
    event_name: string
    source: string
    session_id: string | null
    device_id: number | null
    entity_type: string | null
    entity_id: number | null
    occurred_at: string
    received_at: string
    properties: Record<string, unknown>
    attribution: Record<string, unknown>
  }>
  consents: Array<{
    id: number
    purpose: string
    channel: string
    is_granted: boolean
    source: string
    policy_version: string | null
    granted_at: string | null
    revoked_at: string | null
    last_changed_at: string
  }>
  attribution: {
    first_source: string | null
    first_medium: string | null
    first_campaign: string | null
    first_content: string | null
    first_term: string | null
    first_referrer: string | null
    first_landing_page: string | null
    first_touch_at: string | null
    last_source: string | null
    last_medium: string | null
    last_campaign: string | null
    last_content: string | null
    last_term: string | null
    last_referrer: string | null
    last_landing_page: string | null
    last_touch_at: string | null
    install_source: string | null
  } | null
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
  attachment_items: Array<{
    id: number
    url: string
    mime_type: string | null
    moderation_status: "approved" | "rejected" | "pending"
    created_at: string
  }>
  spam_score: number
  profanity_flag: boolean
  duplicate_flag: boolean
  suspicious_ip_flag: boolean
  moderation_flags: Record<string, unknown>
  internal_moderation_comment: string | null
  submitter_ip: string | null
  appeal_status: string
  moderated_at: string | null
  restored_at: string | null
  customer_notified_at: string | null
  created_at: string
  updated_at: string
}

export type ReviewModerationEvent = {
  id: number
  action: string
  actor_name: string | null
  comment: string | null
  before_json: Record<string, unknown> | null
  after_json: Record<string, unknown> | null
  metadata_json: Record<string, unknown>
  created_at: string
}

export type Banner = {
  id: number
  image_path: string
  desktop_image_path: string | null
  mobile_image_path: string | null
  title: string | null
  inner_link: string | null
  outer_link: string | null
  priority: number
  archived: boolean
  status: "draft" | "scheduled" | "published" | "archived"
  starts_at: string | null
  ends_at: string | null
  audience_json: Record<string, unknown>
  click_count: number
  impression_count: number
  created_at: string
  updated_at: string
}

export type BannerUpload = {
  image_path: string
  url: string
}

export type BusinessContent = {
  id: number
  code: string
  title_ru: string
  title_en: string
  body_ru: string
  body_en: string
  link_url: string | null
  status: "draft" | "published" | "archived"
  metadata_json: Record<string, unknown>
  version: number
  updated_by_name: string | null
  created_at: string
  updated_at: string
}

export type BusinessContentVersion = {
  id: number
  version: number
  actor_name: string | null
  snapshot_json: Record<string, unknown>
  created_at: string
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
  target_type: string | null
  target_id: string | null
  retry_of_id: number | null
  attempts: number
  max_attempts: number
  counters_json: Record<string, unknown>
  error: string | null
  started_at: string
  heartbeat_at: string | null
  next_attempt_at: string | null
  finished_at: string | null
}

export type IntegrationQueueHealth = {
  queue_available: boolean
  queue_depth: number
  processing_depth: number
  scheduled_depth: number
  queued: number
  running: number
  retrying: number
  failed_24h: number
  stale_running: number
  oldest_pending_at: string | null
}

export type ReadinessCheck = {
  key: string
  label_ru: string
  label_en: string
  status: "ok" | "warning" | "error" | "unknown"
  message_ru: string
  message_en: string
  details: Record<string, unknown>
}

export type WorkerHeartbeat = {
  name: string
  status: "ok" | "warning" | "unknown"
  last_seen_at: string | null
  stale_after_seconds: number
}

export type ProductionReadiness = {
  overall_status: "ok" | "warning" | "error" | "unknown"
  generated_at: string
  public_host: string | null
  checklist_summary: Record<"ok" | "warning" | "error" | "unknown", number>
  checks: ReadinessCheck[]
  workers: WorkerHeartbeat[]
}

export type SavedView = {
  id: number
  owner_user_id: number
  resource: string
  name: string
  state_json: Record<string, unknown>
  is_shared: boolean
  created_at: string
  updated_at: string
}

export type AdminExport = {
  id: number
  resource: string
  format: "csv" | "xlsx"
  status: string
  rows: number | null
  file_name: string | null
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
  description_ru: string
  description_en: string
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

export type AdminInvitation = {
  id: number
  email: string
  role_codes: string[]
  role_names_ru: string[]
  role_names_en: string[]
  invited_by_name: string
  status: "pending" | "accepted" | "expired" | "revoked"
  created_at: string
  expires_at: string
  accepted_at: string | null
  revoked_at: string | null
  last_sent_at: string
  send_count: number
}

export type AdminInvitationPreview = {
  email: string
  role_codes: string[]
  role_names_ru: string[]
  role_names_en: string[]
  invited_by_name: string
  status: "pending" | "accepted" | "expired" | "revoked"
  expires_at: string
  existing_user: boolean
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

export type ReferralSummary = {
  profiles_count: number
  active_referrers_count: number
  total_discount_base: string
  average_discount_percent: string
  max_discount_percent: string
  discount_bands: Array<{ band: string; count: number }>
}

export type CustomerSegment = {
  id: number
  owner_user_id: number
  owner_name: string
  name: string
  filters_json: SegmentDefinition
  is_shared: boolean
  segment_type: "dynamic" | "static"
  audience_count: number
  push_reachable_count: number
  snapshot_version: number
  snapshot_at: string | null
  snapshot_count: number
  created_at: string
  updated_at: string
}

export type SegmentCondition = {
  field: string
  operator: string
  value?: unknown
}

export type SegmentDefinition = {
  version: 2
  combinator: "and" | "or"
  conditions: Array<SegmentCondition | SegmentDefinition>
  exclusions: number[]
}

export type AudiencePreview = {
  count: number
  push_reachable_count: number
  sample: Array<{
    id: number
    name: string
    surname: string
    email: string | null
    phone_number: string | null
    orders_count: number
    paid_total: string
    last_order_at: string | null
  }>
}

export type SegmentHistory = {
  id: number
  action: string
  actor_name: string | null
  before_json: Record<string, unknown> | null
  after_json: Record<string, unknown> | null
  metadata_json: Record<string, unknown>
  created_at: string
}

export type AdminTask = {
  id: number
  title: string
  description: string | null
  status: "open" | "in_progress" | "done" | "canceled"
  priority: "low" | "normal" | "high" | "urgent"
  due_at: string | null
  completed_at: string | null
  sla_policy_id: number | null
  response_due_at: string | null
  resolution_due_at: string | null
  first_started_at: string | null
  sla_breached_at: string | null
  customer_user_id: number | null
  customer_name: string | null
  order_id: number | null
  order_code: string | null
  assignee_user_id: number
  assignee_name: string
  created_by_name: string | null
  created_at: string
  updated_at: string
}

export type AssigneeOption = { user_id: number; name: string }

export type PushCampaign = {
  id: number
  name: string
  title: string
  body: string
  deep_link: string | null
  template_id: number | null
  template_name: string | null
  goal: string | null
  utm_json: Record<string, string>
  status: "draft" | "scheduled" | "queued" | "running" | "completed" | "failed" | "canceled"
  segment_id: number | null
  segment_name: string | null
  audience_count: number
  sent_count: number
  skipped_count: number
  failed_count: number
  opened_count: number
  clicked_count: number
  delivery_rate: string
  click_rate: string
  scheduled_at: string | null
  started_at: string | null
  finished_at: string | null
  error: string | null
  created_at: string
  updated_at: string
}

export type PushCampaignTemplate = {
  id: number
  code: string
  category: string
  name_ru: string
  name_en: string
  title_ru: string
  title_en: string
  body_ru: string
  body_en: string
  deep_link: string | null
  goal: string | null
  is_active: boolean
}

export type PushCampaignPreview = {
  title: string
  body: string
  deep_link: string | null
  segment_id: number
  segment_name: string
  audience_count: number
  push_reachable_count: number
  estimated_send_count: number
  warnings: string[]
}

export type PushCampaignRecipient = {
  id: number
  user_id: number
  customer_name: string
  customer_email: string | null
  status: string
  attempts: number
  error: string | null
  sent_at: string | null
  opened_at: string | null
  clicked_at: string | null
}

export type PushCampaignMetrics = {
  campaign_id: number
  audience_count: number
  sent_count: number
  skipped_count: number
  failed_count: number
  opened_count: number
  clicked_count: number
  pending_count: number
  delivery_rate: string
  click_rate: string
  failure_rate: string
}

export type MarketingAutomation = {
  id: number
  code: string
  name_ru: string
  name_en: string
  is_enabled: boolean
  settings_json: Record<string, unknown>
  last_run_at: string | null
  last_result_json: Record<string, unknown>
  last_error: string | null
  updated_at: string
}

export type OrderAutomationRule = {
  id: number
  name: string
  description: string | null
  is_enabled: boolean
  priority: number
  conditions_json: {
    status_codes?: OrderStatusCode[]
    payment_statuses?: string[]
    min_age_minutes?: number
    missing_delivery?: boolean
    missing_moysklad?: boolean
    only_active?: boolean
  }
  action_json: Record<string, unknown> & { kind?: "create_task" | "queue_operation" | "push_customer" }
  created_by_name: string | null
  last_run_at: string | null
  last_match_count: number
  last_error: string | null
  executions_count: number
  created_at: string
  updated_at: string
}

export type OrderAutomationExecution = {
  id: number
  rule_id: number
  order_id: number
  order_code: string
  action_kind: string
  status: string
  result_json: Record<string, unknown>
  error: string | null
  executed_at: string
}

export type OrderAutomationPreview = {
  matched: number
  sample: Array<{
    order_id: number
    order_code: string
    status_code: OrderStatusCode
    payment_status: string
    customer_name: string
    created_at: string
  }>
}

export type OrderAutomationPreset = {
  code: string
  name_ru: string
  name_en: string
  description_ru: string
  description_en: string
  priority: number
  conditions_json: OrderAutomationRule["conditions_json"]
  action_json: Record<string, unknown>
  exists: boolean
  rule_id: number | null
}

export type OrderAutomationPresetApplyResponse = {
  created: number
  skipped: number
  items: OrderAutomationPreset[]
}

export type SlaPolicy = {
  id: number
  priority: "low" | "normal" | "high" | "urgent"
  name_ru: string
  name_en: string
  response_minutes: number
  resolution_minutes: number
  is_enabled: boolean
  updated_at: string
}

export type SlaSummary = {
  assignee_user_id: number
  assignee_name: string
  open_tasks: number
  breached_tasks: number
  completed_30d: number
  on_time_30d: number
  compliance_percent: string
}

export type AdminAlert = {
  id: number
  severity: "info" | "warning" | "error"
  source: string
  code: string
  title_ru: string
  title_en: string
  message: string
  entity_type: string | null
  entity_id: string | null
  path: string | null
  occurrence_count: number
  is_read: boolean
  last_occurred_at: string
  resolved_at: string | null
  created_at: string
}

export type AlertPage = {
  items: AdminAlert[]
  unread_count: number
  total: number
}

export type DashboardPreference = {
  widgets: string[]
  updated_at: string | null
}

export type SupportConversationStatus = "new" | "open" | "waiting_customer" | "waiting_team" | "resolved" | "spam"
export type CrmPriority = "low" | "normal" | "high" | "urgent"

export type SupportAttachment = {
  id: number
  original_filename: string
  mime_type: string
  size_bytes: number
  download_url: string
}

export type SupportMessage = {
  id: number
  sender_type: "user" | "admin" | "system"
  body: string
  author_user_id: number | null
  author_name: string
  author_role: string | null
  is_internal: boolean
  delivered_at: string | null
  read_at: string | null
  attachments: SupportAttachment[]
  created_at: string
  updated_at: string
}

export type SupportConversation = {
  id: number
  customer_user_id: number
  customer_name: string
  customer_email: string | null
  customer_phone: string | null
  subject: string | null
  status: SupportConversationStatus
  priority: CrmPriority
  assignee_user_id: number | null
  assignee_name: string | null
  order_id: number | null
  order_code: string | null
  response_due_at: string | null
  resolution_due_at: string | null
  first_responded_at: string | null
  resolved_at: string | null
  last_message_at: string | null
  sla_breached_at: string | null
  admin_unread_count: number
  customer_unread_count: number
  last_message_preview: string | null
  created_at: string
  updated_at: string
}

export type SupportConversationDetail = SupportConversation & {
  messages: SupportMessage[]
}

export type AIChatListItem = {
  id: number
  user_id: number
  customer_name: string
  customer_email: string | null
  messages_count: number
  user_messages_count: number
  total_tokens: number
  last_message: string | null
  last_activity_at: string
  created_at: string
}

export type AIChatMessage = {
  id: number
  sender: "user" | "ai" | string
  text: string
  context: Record<string, unknown>
  attachments: Array<{
    id: number
    name: string
    mime_type: string | null
    size_bytes: number
    url: string
  }>
  usage: {
    input_tokens: number
    cached_input_tokens: number
    output_tokens: number
    bot_model: string
    openai_model: string
  } | null
  created_at: string
}

export type AIChatAction = {
  id: number
  event_name: "ai_chat_message_sent" | "ai_recommendation_shown" | "ai_action_clicked" | "ai_action_completed" | string
  source: string
  message_id: number | null
  action_id: string | null
  action_type: string | null
  product_id: number | null
  variant_id: number | null
  basket_item_id: number | null
  properties: Record<string, unknown>
  occurred_at: string
}

export type AIChatDetail = {
  id: number
  user_id: number
  customer_name: string
  customer_email: string | null
  customer_phone: string | null
  conversation_id: string
  current_tokens: number
  total_tokens: number
  messages: AIChatMessage[]
  actions: AIChatAction[]
  created_at: string
  updated_at: string
}

export type LeadStatus = "new" | "contacted" | "interested" | "waiting" | "converted" | "lost"

export type CrmLead = {
  id: number
  title: string
  source: "manual" | "support" | "ai_chat" | "customer_intelligence" | string
  status: LeadStatus
  priority: CrmPriority
  score: number
  customer_user_id: number | null
  customer_name: string | null
  conversation_id: number | null
  product_id: number | null
  product_name: string | null
  category_id: number | null
  category_name: string | null
  owner_user_id: number | null
  owner_name: string | null
  converted_order_id: number | null
  converted_order_code: string | null
  contact_name: string | null
  contact_email: string | null
  contact_phone: string | null
  description: string | null
  next_action_at: string | null
  lost_reason: string | null
  converted_at: string | null
  lost_at: string | null
  created_at: string
  updated_at: string
}

export type CrmLeadDetail = CrmLead & {
  stage_history: Array<{
    id: number
    from_status: string | null
    to_status: string
    changed_by_name: string | null
    reason: string | null
    created_at: string
  }>
  notes: Array<{
    id: number
    body: string
    author_name: string | null
    created_at: string
    updated_at: string
  }>
}
