export type AIUsageDailyPoint = {
  period: string
  period_end: string | null
  requests: number
  successful_requests: number
  failed_requests: number | null
  unique_users: number
  input_tokens: number
  cached_input_tokens: number
  output_tokens: number
  total_tokens: number
  cost_usd: number | null
}

export type AIUsageBreakdownItem = {
  key: string
  label: string
  model: string | null
  requests: number
  unique_users: number
  input_tokens: number
  cached_input_tokens: number
  output_tokens: number
  total_tokens: number
  cost_usd: number | null
}

export type AIUsageFunnelItem = {
  key: string
  label: string
  events: number
  unique_users: number
}

export type AIUsageTopUser = {
  account_id: string
  label: string | null
  contact: string | null
  requests: number
  total_tokens: number
  cost_usd: number | null
  last_activity_at: string | null
}

export type AIUsageSource = {
  source: "app" | "bitrix" | "telegram"
  label: string
  configured: boolean
  start_date: string
  end_date: string
  trend_granularity: "daily" | "weekly" | "monthly"
  requests: number
  successful_requests: number
  failed_requests: number | null
  unique_users: number
  conversations: number | null
  user_messages: number | null
  assistant_messages: number | null
  input_tokens: number
  cached_input_tokens: number
  output_tokens: number
  total_tokens: number
  cache_percent: number
  average_tokens_per_request: number
  average_latency_ms: number | null
  cost_usd: number | null
  current_model: string | null
  daily: AIUsageDailyPoint[]
  breakdown: AIUsageBreakdownItem[]
  funnel: AIUsageFunnelItem[]
  top_users: AIUsageTopUser[]
  notes: string[]
  error: string | null
}

export type AIUsageOverview = {
  days: number
  generated_at: string
  requests: number
  successful_requests: number
  failed_requests: number
  unique_users_sum: number
  input_tokens: number
  cached_input_tokens: number
  output_tokens: number
  total_tokens: number
  cost_usd: number | null
  sources: AIUsageSource[]
}
