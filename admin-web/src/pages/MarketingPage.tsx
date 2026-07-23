import { CameraOutlined, DeleteOutlined, DownloadOutlined, EditOutlined, EyeOutlined, HistoryOutlined, PlusOutlined, RocketOutlined } from "@ant-design/icons"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Alert, Button, Card, Col, DatePicker, Drawer, Form, Input, InputNumber, List, Modal, Progress, Row, Select, Space, Statistic, Switch, Table, Tabs, Tag, Typography, message } from "antd"
import dayjs, { type Dayjs } from "dayjs"
import { useMemo, useState } from "react"
import { apiDownload, apiRequest } from "../api/client"
import type { AudiencePreview, CustomerSegment, MarketingAutomation, Page, PushCampaign, PushCampaignMetrics, PushCampaignPreview, PushCampaignRecipient, PushCampaignTemplate, ReferralProfile, ReferralSummary, SegmentDefinition, SegmentHistory } from "../api/types"
import { useAuth } from "../auth/AuthProvider"
import { PageHeader } from "../components/PageHeader"
import { useLanguage } from "../i18n/LanguageProvider"
import { dateTime, money } from "../utils/format"

type SegmentConditionForm = { field: string; operator: string; value?: string | number | boolean | string[] }
type SegmentForm = {
  name: string
  is_shared: boolean
  segment_type: "dynamic" | "static"
  combinator: "and" | "or"
  conditions: SegmentConditionForm[]
  exclusions: number[]
}
type CampaignForm = { name: string; title: string; body: string; deep_link?: string; segment_id: number; template_id?: number; goal?: string; utm_source?: string; utm_campaign?: string; utm_content?: string }

const campaignColors: Record<string, string> = { draft: "default", scheduled: "purple", queued: "blue", running: "gold", completed: "green", failed: "red", canceled: "default" }
const segmentFieldTypes: Record<string, "text" | "number" | "boolean" | "date" | "select" | "ids" | "campaign"> = {
  q: "text", is_active: "boolean", is_verified: "boolean", registration_date: "date", last_activity: "date", inactive_days: "number",
  customer_type: "select", order_count: "number", paid_order_count: "number", ltv: "number", average_order_value: "number", last_purchase: "date",
  abandoned_basket: "boolean", favorite_category: "ids", product_views: "number", product_viewed: "ids", cart_activity: "number",
  review_rating: "number", city: "text", region: "text", referral_status: "select", push_available: "boolean", campaign_participation: "campaign",
  platform: "select", app_version: "text", push_permission: "select", install_source: "text", lifecycle_stage: "select", lead_score: "number", event_count: "number", event_name: "select",
}

function defaultCondition(): SegmentConditionForm {
  return { field: "order_count", operator: "gte", value: 1 }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}

function legacyToDefinition(raw: Record<string, unknown>): SegmentDefinition {
  if (raw.version === 2 && Array.isArray(raw.conditions)) return raw as SegmentDefinition
  const conditions: SegmentConditionForm[] = []
  if (typeof raw.q === "string") conditions.push({ field: "q", operator: "contains", value: raw.q })
  if (typeof raw.is_active === "boolean") conditions.push({ field: "is_active", operator: "eq", value: raw.is_active })
  if (typeof raw.is_verified === "boolean") conditions.push({ field: "is_verified", operator: "eq", value: raw.is_verified })
  if (typeof raw.has_push_token === "boolean") conditions.push({ field: "push_available", operator: "eq", value: raw.has_push_token })
  if (typeof raw.min_orders === "number") conditions.push({ field: "order_count", operator: "gte", value: raw.min_orders })
  if (typeof raw.min_paid_total === "number") conditions.push({ field: "ltv", operator: "gte", value: raw.min_paid_total })
  return { version: 2, combinator: "and", conditions, exclusions: [] }
}

export function segmentFilters(values: SegmentForm): SegmentDefinition {
  return {
    version: 2,
    combinator: values.combinator || "and",
    exclusions: values.exclusions || [],
    conditions: (values.conditions || []).filter((condition) => condition.field && condition.operator).map((condition) => ({
      field: condition.field,
      operator: condition.operator,
      value: condition.value,
    })),
  }
}

function formFromSegment(segment: CustomerSegment): SegmentForm {
  const filters = legacyToDefinition(segment.filters_json)
  return {
    name: segment.name,
    is_shared: segment.is_shared,
    segment_type: segment.segment_type,
    combinator: filters.combinator,
    conditions: filters.conditions.filter((condition) => "field" in condition) as SegmentConditionForm[],
    exclusions: filters.exclusions || [],
  }
}

function formatCondition(condition: SegmentConditionForm | Record<string, unknown>, locale: "ru" | "en") {
  const field = String(condition.field || "")
  const operator = String(condition.operator || "")
  const value = isRecord(condition.value) ? JSON.stringify(condition.value) : Array.isArray(condition.value) ? condition.value.join(", ") : String(condition.value ?? "")
  const labels: Record<string, string> = locale === "ru" ? {
    q: "поиск", is_active: "активен", is_verified: "вериф.", registration_date: "регистрация", last_activity: "активность", inactive_days: "неактивен дней",
    customer_type: "тип клиента", order_count: "заказы", paid_order_count: "оплач. заказы", ltv: "LTV", average_order_value: "средний чек", last_purchase: "посл. покупка",
    abandoned_basket: "брош. корзина", favorite_category: "избранные категории", product_views: "просмотры", product_viewed: "смотрел товар", cart_activity: "корзина",
    review_rating: "рейтинг отзывов", city: "город", region: "регион", referral_status: "рефералы", push_available: "push", campaign_participation: "кампания",
    platform: "платформа", app_version: "версия приложения", push_permission: "разрешение push", install_source: "источник установки", lifecycle_stage: "этап клиента", lead_score: "lead score", event_count: "число событий", event_name: "событие",
  } : {}
  return `${labels[field] || field} ${operator} ${value}`
}

function downloadBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = fileName
  link.click()
  URL.revokeObjectURL(url)
}

export function campaignPayload(values: CampaignForm) {
  return {
    name: values.name.trim(),
    title: values.title.trim(),
    body: values.body.trim(),
    deep_link: values.deep_link?.trim() || null,
    segment_id: values.segment_id,
    template_id: values.template_id || null,
    goal: values.goal?.trim() || null,
    utm_json: {
      ...(values.utm_source?.trim() ? { source: values.utm_source.trim() } : {}),
      ...(values.utm_campaign?.trim() ? { campaign: values.utm_campaign.trim() } : {}),
      ...(values.utm_content?.trim() ? { content: values.utm_content.trim() } : {}),
    },
  }
}

export function MarketingPage() {
  const { locale } = useLanguage()
  const { principal, hasPermission } = useAuth()
  const client = useQueryClient()
  const defaultTab = hasPermission("campaigns.read") ? "campaigns" : hasPermission("segments.read") ? "segments" : "referrals"
  const [tab, setTab] = useState(defaultTab)
  const [segmentDrawer, setSegmentDrawer] = useState(false)
  const [editingSegment, setEditingSegment] = useState<CustomerSegment | null>(null)
  const [preview, setPreview] = useState<AudiencePreview | null>(null)
  const [customersSegment, setCustomersSegment] = useState<CustomerSegment | null>(null)
  const [historySegment, setHistorySegment] = useState<CustomerSegment | null>(null)
  const [campaignDrawer, setCampaignDrawer] = useState(false)
  const [editingCampaign, setEditingCampaign] = useState<PushCampaign | null>(null)
  const [campaignPreview, setCampaignPreview] = useState<PushCampaignPreview | null>(null)
  const [detailsCampaign, setDetailsCampaign] = useState<PushCampaign | null>(null)
  const [launchTarget, setLaunchTarget] = useState<PushCampaign | null>(null)
  const [launchAt, setLaunchAt] = useState<Dayjs | null>(null)
  const [automationDrawer, setAutomationDrawer] = useState(false)
  const [editingAutomation, setEditingAutomation] = useState<MarketingAutomation | null>(null)
  const [segmentForm] = Form.useForm<SegmentForm>()
  const [campaignForm] = Form.useForm<CampaignForm>()
  const [automationForm] = Form.useForm()

  const referrals = useQuery({ queryKey: ["referrals"], queryFn: () => apiRequest<ReferralProfile[]>("/referrals/profiles?limit=100&offset=0"), enabled: hasPermission("referrals.read") })
  const referralSummary = useQuery({ queryKey: ["referrals-summary"], queryFn: () => apiRequest<ReferralSummary>("/referrals/summary"), enabled: hasPermission("referrals.read") })
  const segments = useQuery({ queryKey: ["segments"], queryFn: () => apiRequest<CustomerSegment[]>("/segments"), enabled: hasPermission("segments.read") })
  const campaigns = useQuery({ queryKey: ["campaigns"], queryFn: () => apiRequest<Page<PushCampaign>>("/campaigns?limit=100&offset=0"), enabled: hasPermission("campaigns.read"), refetchInterval: 15_000 })
  const campaignTemplates = useQuery({ queryKey: ["campaign-templates"], queryFn: () => apiRequest<PushCampaignTemplate[]>("/campaign-templates"), enabled: hasPermission("campaigns.read") })
  const automations = useQuery({ queryKey: ["automations"], queryFn: () => apiRequest<MarketingAutomation[]>("/automations"), enabled: hasPermission("campaigns.read"), refetchInterval: 60_000 })
  const segmentCustomers = useQuery({ queryKey: ["segment-customers", customersSegment?.id], queryFn: () => apiRequest<Page<AudiencePreview["sample"][number]>>(`/segments/${customersSegment?.id}/customers?limit=100&offset=0`), enabled: Boolean(customersSegment) })
  const segmentHistory = useQuery({ queryKey: ["segment-history", historySegment?.id], queryFn: () => apiRequest<SegmentHistory[]>(`/segments/${historySegment?.id}/history`), enabled: Boolean(historySegment) })
  const campaignMetrics = useQuery({ queryKey: ["campaign-metrics", detailsCampaign?.id], queryFn: () => apiRequest<PushCampaignMetrics>(`/campaigns/${detailsCampaign?.id}/metrics`), enabled: Boolean(detailsCampaign) })
  const campaignRecipients = useQuery({ queryKey: ["campaign-recipients", detailsCampaign?.id], queryFn: () => apiRequest<Page<PushCampaignRecipient>>(`/campaigns/${detailsCampaign?.id}/recipients?limit=100&offset=0`), enabled: Boolean(detailsCampaign) })
  const referralRows = referrals.data || []

  const copy = locale === "ru"
    ? { title: "Маркетинг", description: "Сегменты, push‑кампании и автоматические сценарии", referrals: "Рефералы", segments: "Сегменты", campaigns: "Push‑кампании", automations: "Автоматизация", profiles: "Участники", base: "База скидки", discount: "Текущая скидка", purchases: "Покупки", created: "Создан", newSegment: "Новый сегмент", newCampaign: "Новая кампания", segmentName: "Название сегмента", team: "Доступен команде", dynamic: "Динамический", static: "Статический", makeSnapshot: "Сделать snapshot", snapshot: "Snapshot", preview: "Рассчитать", audience: "Клиентов", reachable: "Доступны по push", save: "Сохранить", filters: "Условия", campaignName: "Внутреннее название", pushTitle: "Заголовок push", pushBody: "Текст сообщения", deepLink: "Путь внутри приложения", segment: "Сегмент", status: "Статус", sent: "Доставлено", launch: "Запустить", launchTitle: "Подтверждение отправки", launchNow: "Отправить сейчас", schedule: "Запланировать", scheduleTime: "Время отправки", launchWarning: "Аудитория фиксируется перед запуском. После подтверждения состав получателей изменить нельзя.", cancel: "Отменить", lastRun: "Последний запуск", enabled: "Включён", disabled: "Выключен", processed: "Обработано", edit: "Изменить", afterDays: "Запуск через, дней", afterHours: "Запуск через, часов", cooldownDays: "Повтор не чаще, дней", cooldownHours: "Повтор не чаще, часов", triggerHint: "Изменения шаблона применяются к следующим автоматическим отправкам.", combinator: "Логика группы", addCondition: "Добавить условие", field: "Поле", operator: "Оператор", value: "Значение", exclusions: "Исключить сегменты", customers: "Клиенты", history: "История", export: "CSV", saved: "Сегмент сохранён", deleted: "Сегмент удалён", snapshotted: "Snapshot сохранён", template: "Шаблон", goal: "Цель", utm: "UTM", previewPush: "Предпросмотр push", applyTemplate: "Применить шаблон", delivery: "Доставка", clicks: "Клики", failures: "Ошибки", details: "Детали", recipients: "Получатели", pending: "Ожидают", opened: "Открыто", clicked: "Клик", activeReferrers: "Активные", avgDiscount: "Средняя скидка", maxDiscount: "Макс. скидка" }
    : { title: "Marketing", description: "Segments, push campaigns and automated journeys", referrals: "Referrals", segments: "Segments", campaigns: "Push campaigns", automations: "Automations", profiles: "Members", base: "Discount base", discount: "Current discount", purchases: "Purchases", created: "Created", newSegment: "New segment", newCampaign: "New campaign", segmentName: "Segment name", team: "Share with team", dynamic: "Dynamic", static: "Static", makeSnapshot: "Create snapshot", snapshot: "Snapshot", preview: "Preview", audience: "Customers", reachable: "Push reachable", save: "Save", filters: "Conditions", campaignName: "Internal name", pushTitle: "Push title", pushBody: "Message body", deepLink: "In-app path", segment: "Segment", status: "Status", sent: "Delivered", launch: "Launch", launchTitle: "Confirm delivery", launchNow: "Send now", schedule: "Schedule", scheduleTime: "Delivery time", launchWarning: "The audience is snapshotted before launch. Recipients cannot be changed after confirmation.", cancel: "Cancel", lastRun: "Last run", enabled: "Enabled", disabled: "Disabled", processed: "Processed", edit: "Edit", afterDays: "Trigger after, days", afterHours: "Trigger after, hours", cooldownDays: "Repeat no sooner than, days", cooldownHours: "Repeat no sooner than, hours", triggerHint: "Template changes apply to future automated sends.", combinator: "Group logic", addCondition: "Add condition", field: "Field", operator: "Operator", value: "Value", exclusions: "Exclude segments", customers: "Customers", history: "History", export: "CSV", saved: "Segment saved", deleted: "Segment deleted", snapshotted: "Snapshot saved", template: "Template", goal: "Goal", utm: "UTM", previewPush: "Push preview", applyTemplate: "Apply template", delivery: "Delivery", clicks: "Clicks", failures: "Failures", details: "Details", recipients: "Recipients", pending: "Pending", opened: "Opened", clicked: "Clicked", activeReferrers: "Active", avgDiscount: "Average discount", maxDiscount: "Max discount" }

  const fieldOptions = useMemo(() => Object.keys(segmentFieldTypes).map((value) => ({ value, label: formatCondition({ field: value, operator: "", value: "" }, locale).trim() })), [locale])
  const operatorOptions = [{ value: "eq", label: "=" }, { value: "neq", label: "≠" }, { value: "gte", label: "≥" }, { value: "lte", label: "≤" }, { value: "before", label: "before" }, { value: "after", label: "after" }, { value: "contains", label: "contains" }]
  const previewSegment = useMutation({
    mutationFn: (values: SegmentForm) => apiRequest<AudiencePreview>("/segments/preview", { method: "POST", body: JSON.stringify({ name: values.name || "Preview", filters_json: segmentFilters(values), is_shared: values.is_shared, segment_type: values.segment_type }) }),
    onSuccess: setPreview,
    onError: (error: Error) => void message.error(error.message),
  })
  const saveSegment = useMutation({
    mutationFn: (values: SegmentForm) => apiRequest<CustomerSegment>(editingSegment ? `/segments/${editingSegment.id}` : "/segments", {
      method: editingSegment ? "PUT" : "POST",
      body: JSON.stringify({ name: values.name.trim(), filters_json: segmentFilters(values), is_shared: values.is_shared, segment_type: values.segment_type, ...(editingSegment ? { expected_updated_at: editingSegment.updated_at } : {}) }),
    }),
    onSuccess: () => { setSegmentDrawer(false); setPreview(null); void client.invalidateQueries({ queryKey: ["segments"] }); void message.success(copy.saved) },
    onError: (error: Error) => void message.error(error.message),
  })
  const snapshotSegment = useMutation({
    mutationFn: (segment: CustomerSegment) => apiRequest(`/segments/${segment.id}/snapshot`, { method: "POST" }),
    onSuccess: () => { void client.invalidateQueries({ queryKey: ["segments"] }); void message.success(copy.snapshotted) },
    onError: (error: Error) => void message.error(error.message),
  })
  const deleteSegment = useMutation({
    mutationFn: (id: number) => apiRequest<void>(`/segments/${id}`, { method: "DELETE" }),
    onSuccess: () => { void client.invalidateQueries({ queryKey: ["segments"] }); void message.success(copy.deleted) },
    onError: (error: Error) => void message.error(error.message),
  })
  const exportSegment = async (segment: CustomerSegment) => {
    try {
      const result = await apiDownload(`/segments/${segment.id}/export.csv`)
      downloadBlob(result.blob, result.fileName || `segment-${segment.id}.csv`)
    } catch (error) {
      void message.error((error as Error).message)
    }
  }
  const saveCampaign = useMutation({
    mutationFn: (values: CampaignForm) => apiRequest<PushCampaign>(editingCampaign ? `/campaigns/${editingCampaign.id}` : "/campaigns", {
      method: editingCampaign ? "PUT" : "POST",
      body: JSON.stringify({ ...campaignPayload(values), ...(editingCampaign ? { expected_updated_at: editingCampaign.updated_at } : {}) }),
    }),
    onSuccess: () => { setCampaignDrawer(false); setCampaignPreview(null); void client.invalidateQueries({ queryKey: ["campaigns"] }); void message.success(locale === "ru" ? "Кампания сохранена" : "Campaign saved") },
    onError: (error: Error) => void message.error(error.message),
  })
  const previewCampaign = useMutation({
    mutationFn: (values: CampaignForm) => apiRequest<PushCampaignPreview>("/campaigns/preview", { method: "POST", body: JSON.stringify({ ...campaignPayload(values), locale }) }),
    onSuccess: setCampaignPreview,
    onError: (error: Error) => void message.error(error.message),
  })
  const launch = useMutation({
    mutationFn: ({ campaign, count }: { campaign: PushCampaign; count: number }) => apiRequest(`/campaigns/${campaign.id}/launch`, { method: "POST", body: JSON.stringify({ expected_updated_at: campaign.updated_at, expected_audience_count: count, scheduled_at: launchAt?.toISOString() || null, idempotency_key: crypto.randomUUID() }) }),
    onSuccess: () => { setLaunchTarget(null); setLaunchAt(null); void client.invalidateQueries({ queryKey: ["campaigns"] }); void message.success(locale === "ru" ? "Кампания поставлена в очередь" : "Campaign queued") },
    onError: (error: Error) => { void client.invalidateQueries({ queryKey: ["segments"] }); void message.error(error.message) },
  })
  const cancelCampaign = useMutation({
    mutationFn: (campaign: PushCampaign) => apiRequest<PushCampaign>(`/campaigns/${campaign.id}/cancel`, { method: "POST", body: JSON.stringify({ expected_updated_at: campaign.updated_at }) }),
    onSuccess: () => { void client.invalidateQueries({ queryKey: ["campaigns"] }); void message.success(locale === "ru" ? "Кампания отменена" : "Campaign canceled") },
    onError: (error: Error) => void message.error(error.message),
  })
  const toggleAutomation = useMutation({
    mutationFn: (row: MarketingAutomation) => apiRequest<MarketingAutomation>(`/automations/${row.id}`, { method: "PATCH", body: JSON.stringify({ is_enabled: !row.is_enabled, settings_json: row.settings_json, expected_updated_at: row.updated_at }) }),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["automations"] }),
    onError: (error: Error) => void message.error(error.message),
  })
  const saveAutomation = useMutation({
    mutationFn: (values: Record<string, unknown>) => {
      if (!editingAutomation) throw new Error("Automation is not selected")
      const settings: Record<string, unknown> = { title: values.title, body: values.body, deep_link: values.deep_link || null }
      if (editingAutomation.code === "inactive_customer") Object.assign(settings, { after_days: values.after_days, cooldown_days: values.cooldown_days })
      if (editingAutomation.code === "abandoned_cart") Object.assign(settings, { after_hours: values.after_hours, cooldown_hours: values.cooldown_hours })
      if (editingAutomation.code === "review_reminder") Object.assign(settings, { after_days: values.after_days })
      return apiRequest<MarketingAutomation>(`/automations/${editingAutomation.id}`, { method: "PATCH", body: JSON.stringify({ is_enabled: editingAutomation.is_enabled, settings_json: settings, expected_updated_at: editingAutomation.updated_at }) })
    },
    onSuccess: () => { setAutomationDrawer(false); void client.invalidateQueries({ queryKey: ["automations"] }); void message.success(locale === "ru" ? "Сценарий сохранён" : "Automation saved") },
    onError: (error: Error) => void message.error(error.message),
  })

  const openSegment = (segment?: CustomerSegment) => {
    setEditingSegment(segment || null)
    setPreview(null)
    segmentForm.setFieldsValue(segment ? formFromSegment(segment) : { name: "", is_shared: false, segment_type: "dynamic", combinator: "and", conditions: [defaultCondition()], exclusions: [] })
    setSegmentDrawer(true)
  }
  const openCampaign = (campaign?: PushCampaign) => {
    setEditingCampaign(campaign || null)
    setCampaignPreview(null)
    campaignForm.setFieldsValue(campaign ? {
      name: campaign.name,
      title: campaign.title,
      body: campaign.body,
      deep_link: campaign.deep_link || undefined,
      segment_id: campaign.segment_id || 0,
      template_id: campaign.template_id || undefined,
      goal: campaign.goal || undefined,
      utm_source: campaign.utm_json?.source,
      utm_campaign: campaign.utm_json?.campaign,
      utm_content: campaign.utm_json?.content,
    } : { name: "", title: "", body: "", segment_id: segments.data?.[0]?.id || 0, utm_source: "admin", utm_campaign: "" })
    setCampaignDrawer(true)
  }
  const openAutomation = (row: MarketingAutomation) => { setEditingAutomation(row); automationForm.setFieldsValue(row.settings_json); setAutomationDrawer(true) }
  const applyTemplate = (templateId: number) => {
    const template = (campaignTemplates.data || []).find((item) => item.id === templateId)
    if (!template) return
    campaignForm.setFieldsValue({
      template_id: template.id,
      title: locale === "ru" ? template.title_ru : template.title_en,
      body: locale === "ru" ? template.body_ru : template.body_en,
      deep_link: template.deep_link || undefined,
      goal: template.goal || undefined,
      utm_campaign: template.code,
    })
    setCampaignPreview(null)
  }
  const launchCount = launchTarget ? segments.data?.find((segment) => segment.id === launchTarget.segment_id)?.push_reachable_count || 0 : 0
  const tabs = useMemo(() => [
    hasPermission("referrals.read") ? { key: "referrals", label: copy.referrals } : null,
    hasPermission("segments.read") ? { key: "segments", label: copy.segments } : null,
    hasPermission("campaigns.read") ? { key: "campaigns", label: copy.campaigns } : null,
    hasPermission("campaigns.read") ? { key: "automations", label: copy.automations } : null,
  ].filter(Boolean) as Array<{ key: string; label: string }>, [copy.automations, copy.campaigns, copy.referrals, copy.segments, hasPermission])
  const pageAction = tab === "segments" && hasPermission("segments.manage") ? <Button type="primary" icon={<PlusOutlined />} onClick={() => openSegment()}>{copy.newSegment}</Button> : tab === "campaigns" && hasPermission("campaigns.manage") ? <Button type="primary" icon={<PlusOutlined />} onClick={() => openCampaign()}>{copy.newCampaign}</Button> : null

  const renderValueInput = (field: number) => {
    const selectedField = segmentForm.getFieldValue(["conditions", field, "field"]) as string
    const type = segmentFieldTypes[selectedField] || "text"
    if (type === "boolean") return <Select options={[{ value: true, label: locale === "ru" ? "Да" : "Yes" }, { value: false, label: locale === "ru" ? "Нет" : "No" }]} />
    if (type === "number") return <InputNumber style={{ width: "100%" }} />
    if (type === "date") return <Input type="datetime-local" />
    if (type === "ids") return <Select mode="tags" tokenSeparators={[","]} />
  if (type === "campaign") return <InputNumber min={1} style={{ width: "100%" }} />
    if (selectedField === "customer_type") return <Select options={[{ value: "first_time", label: "first_time" }, { value: "repeat", label: "repeat" }, { value: "no_orders", label: "no_orders" }]} />
    if (selectedField === "referral_status") return <Select options={[{ value: "has_referral", label: "has_referral" }, { value: "no_referral", label: "no_referral" }, { value: "discount_active", label: "discount_active" }]} />
    if (selectedField === "platform") return <Select options={["ios", "android", "web"].map((value) => ({ value, label: value }))} />
    if (selectedField === "push_permission") return <Select options={["granted", "denied", "undetermined", "provisional", "unknown"].map((value) => ({ value, label: value }))} />
    if (selectedField === "lifecycle_stage") return <Select options={["new", "engaged", "interested", "high_intent", "customer", "repeat_customer"].map((value) => ({ value, label: value }))} />
    if (selectedField === "event_name") return <Select showSearch options={["app_opened", "product_viewed", "category_viewed", "search_submitted", "banner_clicked", "push_opened", "push_clicked", "cart_item_added", "cart_item_removed", "checkout_started", "checkout_failed", "order_created", "order_paid"].map((value) => ({ value, label: value }))} />
    return <Input />
  }

  return <div className="page-stack">
    <PageHeader title={copy.title} description={copy.description} actions={pageAction} />
    <Tabs activeKey={tab} items={tabs} onChange={setTab} />

    {tab === "referrals" ? <>
      <Row gutter={[16, 16]}>
        <Col xs={24} md={6}><Card><Statistic title={copy.profiles} value={referralSummary.data?.profiles_count ?? referralRows.length} /></Card></Col>
        <Col xs={24} md={6}><Card><Statistic title={copy.activeReferrers} value={referralSummary.data?.active_referrers_count ?? 0} /></Card></Col>
        <Col xs={24} md={6}><Card><Statistic title={copy.base} value={money(referralSummary.data?.total_discount_base ?? 0, "RUB", locale)} /></Card></Col>
        <Col xs={24} md={6}><Card><Statistic title={copy.avgDiscount} value={`${referralSummary.data?.average_discount_percent ?? "0.00"}%`} suffix={<Typography.Text type="secondary">max {referralSummary.data?.max_discount_percent ?? "0.00"}%</Typography.Text>} /></Card></Col>
      </Row>
      <Table<ReferralProfile> rowKey="id" loading={referrals.isLoading} dataSource={referralRows} pagination={{ pageSize: 25 }} columns={[{ title: "User ID", dataIndex: "user_id" }, { title: copy.purchases, dataIndex: "total_purchases", render: (value: string) => money(value, "RUB", locale) }, { title: copy.base, dataIndex: "referral_discount_base_total", render: (value: string) => money(value, "RUB", locale) }, { title: copy.discount, dataIndex: "current_discount_percent", render: (value: string) => <Tag color="green">{value}%</Tag> }, { title: copy.created, dataIndex: "created_at", render: (value: string) => dateTime(value, locale) }]} />
    </> : null}

    {tab === "segments" ? <Table<CustomerSegment> rowKey="id" loading={segments.isLoading} dataSource={segments.data} pagination={false} columns={[
      { title: copy.segmentName, key: "name", render: (_: unknown, row) => <div className="table-primary"><strong>{row.name}</strong><small>{row.is_shared ? copy.team : row.owner_name}</small></div> },
      { title: copy.status, key: "type", render: (_: unknown, row) => <Space><Tag color={row.segment_type === "static" ? "purple" : "blue"}>{row.segment_type === "static" ? copy.static : copy.dynamic}</Tag>{row.snapshot_at ? <Typography.Text type="secondary">v{row.snapshot_version} · {dateTime(row.snapshot_at, locale)}</Typography.Text> : null}</Space> },
      { title: copy.audience, dataIndex: "audience_count", align: "right" },
      { title: copy.reachable, dataIndex: "push_reachable_count", align: "right", render: (value: number, row) => <Space><Progress type="circle" size={30} showInfo={false} percent={row.audience_count ? Math.round(value / row.audience_count * 100) : 0} />{value}</Space> },
      { title: copy.filters, dataIndex: "filters_json", render: (value: SegmentDefinition) => <Typography.Text type="secondary">{value.conditions?.map((item) => "field" in item ? formatCondition(item, locale) : item.combinator).join(" · ") || "—"}</Typography.Text> },
      { title: "", align: "right", render: (_: unknown, row) => <Space>
        <Button size="small" icon={<EyeOutlined />} onClick={() => setCustomersSegment(row)}>{copy.customers}</Button>
        <Button size="small" icon={<HistoryOutlined />} onClick={() => setHistorySegment(row)}>{copy.history}</Button>
        <Button size="small" icon={<DownloadOutlined />} onClick={() => void exportSegment(row)}>{copy.export}</Button>
        {row.owner_user_id === principal?.user.id && hasPermission("segments.manage") ? <><Button size="small" icon={<CameraOutlined />} loading={snapshotSegment.isPending} onClick={() => snapshotSegment.mutate(row)}>{copy.snapshot}</Button><Button size="small" icon={<EditOutlined />} onClick={() => openSegment(row)}>{copy.edit}</Button><Button size="small" danger type="text" icon={<DeleteOutlined />} loading={deleteSegment.isPending} onClick={() => deleteSegment.mutate(row.id)} /></> : null}
      </Space> },
    ]} /> : null}

    {tab === "campaigns" ? <Table<PushCampaign> rowKey="id" loading={campaigns.isLoading} dataSource={campaigns.data?.items} pagination={{ pageSize: 25 }} columns={[
      { title: copy.campaignName, key: "name", render: (_: unknown, row) => <div className="table-primary"><strong>{row.name}</strong><small>{row.template_name || row.title}</small></div> },
      { title: copy.segment, dataIndex: "segment_name", render: (value: string | null) => value || "—" },
      { title: copy.audience, dataIndex: "audience_count", align: "right" },
      { title: copy.sent, key: "sent", align: "right", render: (_: unknown, row) => row.status === "running" ? <Progress percent={row.audience_count ? Math.round(row.sent_count / row.audience_count * 100) : 0} size="small" /> : row.sent_count },
      { title: copy.delivery, key: "delivery", align: "right", render: (_: unknown, row) => `${row.delivery_rate}%` },
      { title: copy.clicks, key: "clicks", align: "right", render: (_: unknown, row) => `${row.click_rate}%` },
      { title: copy.status, dataIndex: "status", render: (value: string) => <Tag color={campaignColors[value]}>{value}</Tag> },
      { title: copy.created, dataIndex: "created_at", render: (value: string) => dateTime(value, locale) },
      { title: "", align: "right", render: (_: unknown, row) => <Space><Button size="small" icon={<EyeOutlined />} onClick={() => setDetailsCampaign(row)}>{copy.details}</Button>{row.status === "draft" && hasPermission("campaigns.manage") ? <Button size="small" icon={<EditOutlined />} onClick={() => openCampaign(row)}>{copy.edit}</Button> : null}{row.status === "draft" && hasPermission("campaigns.send") ? <Button size="small" type="primary" icon={<RocketOutlined />} disabled={!segments.data?.find((segment) => segment.id === row.segment_id)?.push_reachable_count} onClick={() => setLaunchTarget(row)}>{copy.launch}</Button> : null}{["scheduled", "queued"].includes(row.status) && hasPermission("campaigns.send") ? <Button size="small" danger onClick={() => cancelCampaign.mutate(row)}>{copy.cancel}</Button> : null}</Space> },
    ]} /> : null}

    {tab === "automations" ? <Row gutter={[16, 16]}>{(automations.data || []).map((row) => <Col xs={24} lg={12} key={row.id}><Card className="automation-card"><div className="automation-card-header"><div><Typography.Title level={5}>{locale === "ru" ? row.name_ru : row.name_en}</Typography.Title><Typography.Text type="secondary">{copy.lastRun}: {dateTime(row.last_run_at, locale)}</Typography.Text></div><Switch checked={row.is_enabled} disabled={!hasPermission("campaigns.manage")} loading={toggleAutomation.isPending} onChange={() => toggleAutomation.mutate(row)} /></div><Typography.Paragraph type="secondary" ellipsis={{ rows: 2 }}>{String(row.settings_json.body || "")}</Typography.Paragraph><Space><Tag color={row.is_enabled ? "green" : "default"}>{row.is_enabled ? copy.enabled : copy.disabled}</Tag><Typography.Text>{copy.processed}: {String(row.last_result_json.processed ?? 0)}</Typography.Text>{hasPermission("campaigns.manage") ? <Button size="small" icon={<EditOutlined />} onClick={() => openAutomation(row)}>{copy.edit}</Button> : null}</Space>{row.last_error ? <Alert type="error" showIcon message={row.last_error} /> : null}</Card></Col>)}</Row> : null}

    <Drawer width={760} open={segmentDrawer} title={editingSegment ? copy.edit : copy.newSegment} onClose={() => setSegmentDrawer(false)} extra={<Button type="primary" loading={saveSegment.isPending} onClick={() => void segmentForm.validateFields().then((values) => saveSegment.mutate(values))}>{copy.save}</Button>}>
      <Form form={segmentForm} layout="vertical" requiredMark={false}>
        <Row gutter={12}><Col span={14}><Form.Item name="name" label={copy.segmentName} rules={[{ required: true, min: 1, max: 120 }]}><Input /></Form.Item></Col><Col span={5}><Form.Item name="segment_type" label={copy.status}><Select options={[{ value: "dynamic", label: copy.dynamic }, { value: "static", label: copy.static }]} /></Form.Item></Col><Col span={5}><Form.Item name="combinator" label={copy.combinator}><Select options={[{ value: "and", label: "AND" }, { value: "or", label: "OR" }]} /></Form.Item></Col></Row>
        <Form.Item name="is_shared" valuePropName="checked"><Switch /> <span className="switch-label">{copy.team}</span></Form.Item>
        <Form.List name="conditions">{(fields, { add, remove }) => <Space direction="vertical" style={{ width: "100%" }} size={10}>
          {fields.map((field) => <Card size="small" key={field.key} className="segment-condition-card">
            <Row gutter={8} align="bottom">
              <Col span={7}><Form.Item name={[field.name, "field"]} label={copy.field} rules={[{ required: true }]}><Select showSearch options={fieldOptions} onChange={() => segmentForm.setFieldValue(["conditions", field.name, "value"], undefined)} /></Form.Item></Col>
              <Col span={5}><Form.Item name={[field.name, "operator"]} label={copy.operator} rules={[{ required: true }]}><Select options={operatorOptions} /></Form.Item></Col>
              <Col span={10}><Form.Item name={[field.name, "value"]} label={copy.value}>{renderValueInput(field.name)}</Form.Item></Col>
              <Col span={2}><Button danger type="text" icon={<DeleteOutlined />} onClick={() => remove(field.name)} /></Col>
            </Row>
          </Card>)}
          <Button block icon={<PlusOutlined />} onClick={() => add(defaultCondition())}>{copy.addCondition}</Button>
        </Space>}</Form.List>
        <Form.Item name="exclusions" label={copy.exclusions} style={{ marginTop: 16 }}><Select mode="multiple" options={(segments.data || []).filter((segment) => segment.id !== editingSegment?.id).map((segment) => ({ value: segment.id, label: segment.name }))} /></Form.Item>
        <Button block loading={previewSegment.isPending} onClick={() => void segmentForm.validateFields().then((values) => previewSegment.mutate(values))}>{copy.preview}</Button>
        {preview ? <div className="audience-preview"><Row gutter={12}><Col span={12}><Statistic title={copy.audience} value={preview.count} /></Col><Col span={12}><Statistic title={copy.reachable} value={preview.push_reachable_count} /></Col></Row><Table rowKey="id" size="small" dataSource={preview.sample} pagination={false} columns={[{ title: copy.customers, render: (_: unknown, row: AudiencePreview["sample"][number]) => `${row.name} ${row.surname}`.trim() }, { title: "LTV", dataIndex: "paid_total", render: (value: string) => money(value, "RUB", locale) }]} /></div> : null}
      </Form>
    </Drawer>

    <Drawer width={680} open={Boolean(customersSegment)} title={`${copy.customers}: ${customersSegment?.name || ""}`} onClose={() => setCustomersSegment(null)}>
      <Table rowKey="id" loading={segmentCustomers.isLoading} dataSource={segmentCustomers.data?.items} pagination={false} columns={[{ title: copy.customers, render: (_: unknown, row: AudiencePreview["sample"][number]) => <div className="table-primary"><strong>{row.name} {row.surname}</strong><small>{row.email || row.phone_number || "—"}</small></div> }, { title: "Orders", dataIndex: "orders_count", align: "right" }, { title: "LTV", dataIndex: "paid_total", render: (value: string) => money(value, "RUB", locale) }, { title: "Last", dataIndex: "last_order_at", render: (value: string | null) => dateTime(value, locale) }]} />
    </Drawer>
    <Drawer width={560} open={Boolean(historySegment)} title={`${copy.history}: ${historySegment?.name || ""}`} onClose={() => setHistorySegment(null)}>
      <List loading={segmentHistory.isLoading} dataSource={segmentHistory.data || []} renderItem={(item) => <List.Item><List.Item.Meta title={<Space><Tag>{item.action}</Tag>{item.actor_name || "—"}</Space>} description={dateTime(item.created_at, locale)} /></List.Item>} />
    </Drawer>

    <Drawer width={560} open={campaignDrawer} title={editingCampaign ? copy.edit : copy.newCampaign} onClose={() => setCampaignDrawer(false)} extra={<Button type="primary" loading={saveCampaign.isPending} onClick={() => void campaignForm.validateFields().then((values) => saveCampaign.mutate(values))}>{copy.save}</Button>}>
      <Form form={campaignForm} layout="vertical" requiredMark={false}>
        <Form.Item name="name" label={copy.campaignName} rules={[{ required: true, min: 1, max: 160 }]}><Input /></Form.Item>
        <Form.Item name="template_id" label={copy.template}><Select allowClear loading={campaignTemplates.isLoading} options={(campaignTemplates.data || []).map((template) => ({ value: template.id, label: `${locale === "ru" ? template.name_ru : template.name_en} · ${template.category}` }))} onChange={(value) => value ? applyTemplate(value) : null} /></Form.Item>
        <Form.Item name="segment_id" label={copy.segment} rules={[{ required: true }]}><Select options={(segments.data || []).map((segment) => ({ value: segment.id, label: `${segment.name} · ${segment.push_reachable_count}` }))} /></Form.Item>
        <Form.Item name="goal" label={copy.goal}><Input placeholder="sales / retention / recovery" /></Form.Item>
        <Form.Item name="title" label={copy.pushTitle} rules={[{ required: true, min: 1, max: 180 }]}><Input showCount maxLength={180} /></Form.Item>
        <Form.Item name="body" label={copy.pushBody} rules={[{ required: true, min: 1, max: 500 }]}><Input.TextArea rows={5} showCount maxLength={500} /></Form.Item>
        <Form.Item name="deep_link" label={copy.deepLink} rules={[{ pattern: /^\/(?!\/)/, message: "/catalog/products" }]}><Input placeholder="/catalog/products" /></Form.Item>
        <Typography.Text type="secondary">{copy.utm}</Typography.Text>
        <Row gutter={12} style={{ marginTop: 8 }}><Col span={8}><Form.Item name="utm_source"><Input placeholder="source" /></Form.Item></Col><Col span={8}><Form.Item name="utm_campaign"><Input placeholder="campaign" /></Form.Item></Col><Col span={8}><Form.Item name="utm_content"><Input placeholder="content" /></Form.Item></Col></Row>
        <Button block loading={previewCampaign.isPending} onClick={() => void campaignForm.validateFields().then((values) => previewCampaign.mutate(values))}>{copy.previewPush}</Button>
        {campaignPreview ? <Card className="campaign-preview-card" size="small">
          <div className="phone-preview"><Typography.Text strong>{campaignPreview.title}</Typography.Text><Typography.Paragraph>{campaignPreview.body}</Typography.Paragraph><Typography.Text type="secondary">{campaignPreview.deep_link || "—"}</Typography.Text></div>
          <Row gutter={12}><Col span={8}><Statistic title={copy.audience} value={campaignPreview.audience_count} /></Col><Col span={8}><Statistic title={copy.reachable} value={campaignPreview.push_reachable_count} /></Col><Col span={8}><Statistic title={copy.sent} value={campaignPreview.estimated_send_count} /></Col></Row>
          {campaignPreview.warnings.map((warning) => <Alert key={warning} type="warning" showIcon message={warning} />)}
        </Card> : null}
      </Form>
    </Drawer>

    <Drawer width={760} open={Boolean(detailsCampaign)} title={`${copy.details}: ${detailsCampaign?.name || ""}`} onClose={() => setDetailsCampaign(null)}>
      <Row gutter={[12, 12]}>
        <Col xs={12} md={6}><Card><Statistic title={copy.audience} value={campaignMetrics.data?.audience_count ?? detailsCampaign?.audience_count ?? 0} /></Card></Col>
        <Col xs={12} md={6}><Card><Statistic title={copy.delivery} value={`${campaignMetrics.data?.delivery_rate ?? detailsCampaign?.delivery_rate ?? "0.00"}%`} /></Card></Col>
        <Col xs={12} md={6}><Card><Statistic title={copy.clicks} value={`${campaignMetrics.data?.click_rate ?? detailsCampaign?.click_rate ?? "0.00"}%`} /></Card></Col>
        <Col xs={12} md={6}><Card><Statistic title={copy.failures} value={campaignMetrics.data?.failed_count ?? detailsCampaign?.failed_count ?? 0} /></Card></Col>
      </Row>
      <Card className="campaign-message-card">
        <Typography.Text type="secondary">{detailsCampaign?.goal || detailsCampaign?.template_name || "—"}</Typography.Text>
        <Typography.Title level={5}>{detailsCampaign?.title}</Typography.Title>
        <Typography.Paragraph>{detailsCampaign?.body}</Typography.Paragraph>
        <Space wrap>{detailsCampaign?.deep_link ? <Tag>{detailsCampaign.deep_link}</Tag> : null}{Object.entries(detailsCampaign?.utm_json || {}).map(([key, value]) => <Tag key={key}>{key}: {value}</Tag>)}</Space>
      </Card>
      <Table<PushCampaignRecipient> rowKey="id" loading={campaignRecipients.isLoading} dataSource={campaignRecipients.data?.items} pagination={{ pageSize: 25 }} columns={[
        { title: copy.recipients, key: "customer", render: (_: unknown, row) => <div className="table-primary"><strong>{row.customer_name}</strong><small>{row.customer_email || `User ${row.user_id}`}</small></div> },
        { title: copy.status, dataIndex: "status", render: (value: string) => <Tag>{value}</Tag> },
        { title: copy.sent, dataIndex: "sent_at", render: (value: string | null) => dateTime(value, locale) },
        { title: copy.opened, dataIndex: "opened_at", render: (value: string | null) => dateTime(value, locale) },
        { title: copy.clicked, dataIndex: "clicked_at", render: (value: string | null) => dateTime(value, locale) },
      ]} />
    </Drawer>

    <Modal open={Boolean(launchTarget)} title={copy.launchTitle} okText={launchAt ? copy.schedule : copy.launchNow} confirmLoading={launch.isPending} okButtonProps={{ danger: true, disabled: launchCount < 1 }} onCancel={() => { setLaunchTarget(null); setLaunchAt(null) }} onOk={() => launchTarget && launch.mutate({ campaign: launchTarget, count: launchCount })}>
      <Space direction="vertical" size={16} style={{ width: "100%" }}><Alert type="warning" showIcon message={copy.launchWarning} /><Row gutter={12}><Col span={12}><Statistic title={copy.segment} value={launchTarget?.segment_name || "—"} /></Col><Col span={12}><Statistic title={copy.reachable} value={launchCount} /></Col></Row><div><Typography.Text strong>{copy.scheduleTime}</Typography.Text><DatePicker showTime value={launchAt} minDate={dayjs()} style={{ width: "100%", marginTop: 8 }} onChange={setLaunchAt} /></div></Space>
    </Modal>
    <Drawer width={520} open={automationDrawer} title={editingAutomation ? (locale === "ru" ? editingAutomation.name_ru : editingAutomation.name_en) : copy.automations} onClose={() => setAutomationDrawer(false)} extra={<Button type="primary" loading={saveAutomation.isPending} onClick={() => void automationForm.validateFields().then((values) => saveAutomation.mutate(values))}>{copy.save}</Button>}>
      <Alert type="info" showIcon message={copy.triggerHint} className="drawer-alert" />
      <Form form={automationForm} layout="vertical" requiredMark={false}>
        <Form.Item name="title" label={copy.pushTitle} rules={[{ required: true, max: 180 }]}><Input showCount maxLength={180} /></Form.Item>
        <Form.Item name="body" label={copy.pushBody} rules={[{ required: true, max: 500 }]}><Input.TextArea rows={5} showCount maxLength={500} /></Form.Item>
        <Form.Item name="deep_link" label={copy.deepLink} rules={[{ pattern: /^\/(?!\/)/ }]}><Input placeholder="/catalog/products" /></Form.Item>
        {editingAutomation?.code === "inactive_customer" ? <Row gutter={12}><Col span={12}><Form.Item name="after_days" label={copy.afterDays} rules={[{ required: true }]}><InputNumber min={7} max={365} style={{ width: "100%" }} /></Form.Item></Col><Col span={12}><Form.Item name="cooldown_days" label={copy.cooldownDays} rules={[{ required: true }]}><InputNumber min={1} max={365} style={{ width: "100%" }} /></Form.Item></Col></Row> : null}
        {editingAutomation?.code === "abandoned_cart" ? <Row gutter={12}><Col span={12}><Form.Item name="after_hours" label={copy.afterHours} rules={[{ required: true }]}><InputNumber min={1} max={720} style={{ width: "100%" }} /></Form.Item></Col><Col span={12}><Form.Item name="cooldown_hours" label={copy.cooldownHours} rules={[{ required: true }]}><InputNumber min={1} max={720} style={{ width: "100%" }} /></Form.Item></Col></Row> : null}
        {editingAutomation?.code === "review_reminder" ? <Form.Item name="after_days" label={copy.afterDays} rules={[{ required: true }]}><InputNumber min={1} max={365} style={{ width: "100%" }} /></Form.Item> : null}
      </Form>
    </Drawer>
  </div>
}
