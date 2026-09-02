import {
  ClockCircleOutlined,
  BarChartOutlined,
  CustomerServiceOutlined,
  DownloadOutlined,
  MessageOutlined,
  PlusOutlined,
  RobotOutlined,
  SearchOutlined,
  SendOutlined,
  UserAddOutlined,
} from "@ant-design/icons"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  Avatar,
  Alert,
  Badge,
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  Form,
  Input,
  List,
  Modal,
  Row,
  Segmented,
  Select,
  Space,
  Spin,
  Statistic,
  Switch,
  Tabs,
  Tag,
  Table,
  Timeline,
  Typography,
  message,
} from "antd"
import { useEffect, useMemo, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { apiDownload, apiRequest, queryString } from "../api/client"
import type {
  AIChatDetail,
  AIChatBan,
  AIChatListItem,
  AIChatSecurityEvent,
  AIChatSecurityOverview,
  AIChatSecuritySource,
  AssigneeOption,
  Page,
  SupportConversation,
  SupportConversationDetail,
  SupportConversationStatus,
  SupportCustomer,
} from "../api/types"
import type { AIUsageOverview, AIUsageSource } from "../api/aiUsageTypes"
import { PageHeader } from "../components/PageHeader"
import { MetricLineChart } from "../components/MetricLineChart"
import { useAuth } from "../auth/AuthProvider"
import { useLanguage } from "../i18n/LanguageProvider"
import { domainLabel } from "../i18n/domain"
import { dateTime } from "../utils/format"

const statusColors: Record<SupportConversationStatus, string> = {
  new: "blue",
  open: "cyan",
  waiting_customer: "gold",
  waiting_team: "purple",
  resolved: "green",
  spam: "default",
}

const priorityColors = { low: "default", normal: "blue", high: "orange", urgent: "red" } as const

type StartConversationForm = {
  customer_user_id: number
  subject?: string
  body: string
}

function downloadBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = fileName
  anchor.click()
  URL.revokeObjectURL(url)
}

function AIUsageAnalyticsCard() {
  const { locale } = useLanguage()
  const { hasPermission } = useAuth()
  const [days, setDays] = useState(30)
  const analytics = useQuery({
    queryKey: ["ai-usage-analytics", days],
    queryFn: () => apiRequest<AIUsageOverview>(`/ai-chats/analytics${queryString({ days })}`),
    staleTime: 60_000,
    refetchInterval: 300_000,
  })
  const copy = locale === "ru" ? {
    title: "Использование AI по всем каналам",
    requests: "Запросы",
    users: "Пользователи",
    usersSum: "Пользователи по источникам",
    tokens: "Всего токенов",
    success: "Успешно",
    failures: "Ошибки",
    actualCost: "Фактическая стоимость",
    recordedCost: "Учтённая стоимость",
    totalCost: "Общая стоимость",
    source: "Источник",
    conversations: "Диалоги",
    userMessages: "Сообщения пользователей",
    aiMessages: "Ответы AI",
    input: "Входящие токены",
    cached: "Из них кэшировано",
    output: "Исходящие токены",
    cache: "Доля кэша",
    average: "Токенов на ответ",
    latency: "Среднее время ответа",
    model: "Текущая модель",
    trend: "Динамика запросов",
    trendExplanation: "Запросы — все обращения к AI. Успешно — ответы без ошибки. Пользователи — уникальные аккаунты периода. Токены — полный объём входящих и исходящих токенов.",
    breakdown: "Разрез по моделям и ботам",
    topUsers: "Самые активные пользователи",
    customer: "Пользователь",
    lastActivity: "Последняя активность",
    funnel: "Действия пользователей",
    period: "Период",
    unavailable: "Источник не подключён или временно недоступен",
    noData: "За выбранный период данных нет",
    events: "События",
    updated: "Обновлено",
    uniqueNote: "Один человек может присутствовать в нескольких источниках, поэтому это сумма, а не число уникальных людей между системами.",
  } : {
    title: "AI usage across all channels",
    requests: "Requests",
    users: "Users",
    usersSum: "Users by source",
    tokens: "Total tokens",
    success: "Successful",
    failures: "Failures",
    actualCost: "Actual cost",
    recordedCost: "Recorded cost",
    totalCost: "Total cost",
    source: "Source",
    conversations: "Conversations",
    userMessages: "User messages",
    aiMessages: "AI responses",
    input: "Input tokens",
    cached: "Cached input",
    output: "Output tokens",
    cache: "Cache share",
    average: "Tokens per response",
    latency: "Average response time",
    model: "Current model",
    trend: "Request trend",
    trendExplanation: "Requests is every AI request. Successful is responses without an error. Users is distinct accounts in the period. Tokens is total input and output usage.",
    breakdown: "Model and bot breakdown",
    topUsers: "Most active users",
    customer: "User",
    lastActivity: "Last activity",
    funnel: "User actions",
    period: "Period",
    unavailable: "Source is not configured or temporarily unavailable",
    noData: "No data for the selected period",
    events: "Events",
    updated: "Updated",
    uniqueNote: "The same person can use several sources, so this is a sum rather than a cross-system unique-user count.",
  }
  const sourceLabel = (source: AIUsageSource["source"]) => ({
    app: locale === "ru" ? "Приложение" : "Application",
    bitrix: locale === "ru" ? "Сайт Bitrix" : "Bitrix website",
    telegram: locale === "ru" ? "Telegram AI-боты" : "Telegram AI bots",
  }[source])
  const breakdownLabel = (item: { key: string; label: string }) => ({
    professor: locale === "ru" ? "Профессор пептидов" : "Peptide professor",
    dose: locale === "ru" ? "Расчёт дозировок" : "Dose calculator",
    new: locale === "ru" ? "Премиум AI-бот" : "Premium AI bot",
  }[item.key] || item.label)
  const funnelLabel = (key: string) => ({
    ai_chat_message_sent: locale === "ru" ? "Сообщения отправлены" : "Messages sent",
    ai_recommendation_shown: locale === "ru" ? "Рекомендации показаны" : "Recommendations shown",
    ai_action_clicked: locale === "ru" ? "Действия нажаты" : "Actions clicked",
    ai_action_completed: locale === "ru" ? "Действия выполнены" : "Actions completed",
    message_requested: locale === "ru" ? "Запросы отправлены" : "Requests sent",
    response_completed: locale === "ru" ? "Ответы получены" : "Responses completed",
    action_requested: locale === "ru" ? "Действия запрошены" : "Actions requested",
  }[key] || domainLabel(key, locale))
  const noteLabel = (note: string) => ({
    app_actual_cost_from_exact_usage: locale === "ru" ? "Фактическая стоимость рассчитана по точным токенам, сохранённой модели и официальному тарифу OpenAI на дату запроса." : "Actual cost is calculated from exact tokens, the stored model, and the official OpenAI rate effective on the request date.",
    app_cost_has_unsupported_models: locale === "ru" ? "В периоде есть модель без известного официального тарифа; итоговая стоимость для неё не включена." : "The period contains a model without a known official rate; its cost is excluded.",
    app_failed_requests_inferred: locale === "ru" ? "Ошибки приложения определяются как сообщения пользователя без сохранённого AI-ответа." : "Application failures are inferred from user messages without a stored AI response.",
    bitrix_actual_cost_from_exact_usage: locale === "ru" ? "Фактическая стоимость рассчитана по точным токенам и официальному тарифу сохранённой модели на дату запроса." : "Actual cost is calculated from exact tokens and the official rate for the stored model on the request date.",
    bitrix_legacy_model_backfilled: locale === "ru" ? "Для прежних ответов модель восстановлена из подтверждённой конфигурации сервиса; новые ответы сохраняют модель и тарифный снимок." : "For earlier responses, the model was restored from the verified service configuration; new responses store the model and pricing snapshot.",
    bitrix_cost_has_unsupported_models: locale === "ru" ? "В периоде есть модель без известного официального тарифа; итоговая стоимость для неё не включена." : "The period contains a model without a known official rate; its cost is excluded.",
    telegram_failures_not_persisted: locale === "ru" ? "Telegram-хранилище учитывает успешные AI-запросы; ошибки отдельно не сохраняются." : "Telegram storage records successful AI requests; failures are not persisted separately.",
    telegram_cost_is_estimated: locale === "ru" ? "Стоимость Telegram рассчитана по сохранённым токенам и тарифам моделей." : "Telegram cost is calculated from stored tokens and model rates.",
    bitrix_integration_not_configured: locale === "ru" ? "Интеграция статистики Bitrix не настроена." : "Bitrix analytics integration is not configured.",
    telegram_integration_not_configured: locale === "ru" ? "Интеграция статистики Telegram не настроена." : "Telegram analytics integration is not configured.",
  }[note] || note)
  const number = (value: number) => new Intl.NumberFormat(locale === "ru" ? "ru-RU" : "en-US", { maximumFractionDigits: 2 }).format(value)
  const money = (value: number) => new Intl.NumberFormat(locale === "ru" ? "ru-RU" : "en-US", { minimumFractionDigits: 2, maximumFractionDigits: 6 }).format(value)
  const tabs = (analytics.data?.sources || []).map((source) => {
    const sourceCostLabel = source.source === "app" || source.source === "bitrix" ? copy.actualCost : copy.recordedCost
    return {
      key: source.source,
      label: <Space>{sourceLabel(source.source)}{source.error || !source.configured ? <Badge status="error" /> : <Badge status="success" />}</Space>,
      children: source.error || !source.configured ? <Alert type="warning" showIcon message={copy.unavailable} description={source.error || source.notes.map(noteLabel).join(" ")} /> : (
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <Descriptions bordered size="small" column={{ xs: 1, sm: 2, xl: 4 }}>
            <Descriptions.Item label={copy.requests}>{number(source.requests)}</Descriptions.Item>
            <Descriptions.Item label={copy.success}>{number(source.successful_requests)}</Descriptions.Item>
            <Descriptions.Item label={copy.failures}>{source.failed_requests === null ? "—" : number(source.failed_requests)}</Descriptions.Item>
            <Descriptions.Item label={copy.users}>{number(source.unique_users)}</Descriptions.Item>
            <Descriptions.Item label={copy.conversations}>{source.conversations === null ? "—" : number(source.conversations)}</Descriptions.Item>
            <Descriptions.Item label={copy.userMessages}>{source.user_messages === null ? "—" : number(source.user_messages)}</Descriptions.Item>
            <Descriptions.Item label={copy.aiMessages}>{source.assistant_messages === null ? "—" : number(source.assistant_messages)}</Descriptions.Item>
            <Descriptions.Item label={copy.model}>{source.current_model || "—"}</Descriptions.Item>
            <Descriptions.Item label={copy.input}>{number(source.input_tokens)}</Descriptions.Item>
            <Descriptions.Item label={copy.cached}>{number(source.cached_input_tokens)}</Descriptions.Item>
            <Descriptions.Item label={copy.output}>{number(source.output_tokens)}</Descriptions.Item>
            <Descriptions.Item label={copy.tokens}>{number(source.total_tokens)}</Descriptions.Item>
            <Descriptions.Item label={copy.cache}>{number(source.cache_percent)}%</Descriptions.Item>
            <Descriptions.Item label={copy.average}>{number(source.average_tokens_per_request)}</Descriptions.Item>
            <Descriptions.Item label={copy.latency}>{source.average_latency_ms === null ? "—" : `${number(source.average_latency_ms / 1000)} s`}</Descriptions.Item>
            <Descriptions.Item label={sourceCostLabel}>{source.cost_usd === null ? "—" : `$${money(source.cost_usd)}`}</Descriptions.Item>
          </Descriptions>
          <Row gutter={[16, 16]}>
            <Col xs={24} xl={source.funnel.length ? 16 : 24}>
              <Card size="small" title={copy.trend}>
                <MetricLineChart
                  ariaLabel={`${sourceLabel(source.source)}: ${copy.trend}`}
                  emptyText={copy.noData}
                  description={copy.trendExplanation}
                  data={source.daily.some((point) => point.requests > 0) ? source.daily.map((point) => ({
                    key: `${point.period}-${point.period_end || ""}`,
                    label: `${point.period.slice(5)}${point.period_end ? `–${point.period_end.slice(5)}` : ""}`,
                    tooltipLabel: `${point.period}${point.period_end ? ` — ${point.period_end}` : ""}`,
                    values: {
                      requests: point.requests,
                      successful: point.successful_requests,
                      failed: point.failed_requests,
                      users: point.unique_users,
                      tokens: point.total_tokens,
                    },
                  })) : []}
                  series={[
                    { key: "requests", label: copy.requests, color: "#6366f1", formatValue: number },
                    { key: "successful", label: copy.success, color: "#0f766e", formatValue: number },
                    { key: "failed", label: copy.failures, color: "#dc2626", formatValue: number },
                    { key: "users", label: copy.users, color: "#2563eb", formatValue: number },
                    { key: "tokens", label: copy.tokens, color: "#d97706", axis: "right", formatValue: number },
                  ]}
                />
              </Card>
            </Col>
            {source.funnel.length ? <Col xs={24} xl={8}><Card size="small" title={copy.funnel}><Table rowKey="key" size="small" pagination={false} dataSource={source.funnel} columns={[
              { title: copy.events, render: (_: unknown, row) => funnelLabel(row.key) },
              { title: copy.events, dataIndex: "events", align: "right" },
              { title: copy.users, dataIndex: "unique_users", align: "right" },
            ]} /></Card></Col> : null}
          </Row>
          {source.breakdown.length ? <Card size="small" title={copy.breakdown}><Table rowKey="key" size="small" pagination={false} scroll={{ x: 900 }} dataSource={source.breakdown} columns={[
            { title: copy.source, fixed: "left", render: (_: unknown, row) => <div className="table-primary"><strong>{breakdownLabel(row)}</strong>{row.model && row.model !== row.label ? <small>{row.model}</small> : null}</div> },
            { title: copy.requests, dataIndex: "requests", align: "right" },
            { title: copy.users, dataIndex: "unique_users", align: "right" },
            { title: copy.input, dataIndex: "input_tokens", align: "right", render: number },
            { title: copy.cached, dataIndex: "cached_input_tokens", align: "right", render: number },
            { title: copy.output, dataIndex: "output_tokens", align: "right", render: number },
            { title: sourceCostLabel, dataIndex: "cost_usd", align: "right", render: (value: number | null) => value === null ? "—" : `$${money(value)}` },
          ]} /></Card> : null}
          {source.top_users.length ? <Card size="small" title={copy.topUsers}><Table rowKey="account_id" size="small" pagination={source.top_users.length > 10 ? { pageSize: 10, showSizeChanger: false } : false} scroll={{ x: 760 }} dataSource={source.top_users} columns={[
            { title: copy.customer, fixed: "left", render: (_: unknown, row) => <div className="table-primary">{source.source === "app" && hasPermission("customers.read") ? <Link to={`/customers/${row.account_id}`}><strong>{row.label || `#${row.account_id}`}</strong></Link> : <strong>{row.label || `#${row.account_id}`}</strong>}<small>{row.contact || `ID ${row.account_id}`}</small></div> },
            { title: copy.requests, dataIndex: "requests", align: "right" },
            { title: copy.tokens, dataIndex: "total_tokens", align: "right", render: number },
            { title: sourceCostLabel, dataIndex: "cost_usd", align: "right", render: (value: number | null) => value === null ? "—" : `$${money(value)}` },
            { title: copy.lastActivity, dataIndex: "last_activity_at", render: (value: string | null) => value ? dateTime(value, locale) : "—" },
          ]} /></Card> : null}
          {source.notes.length ? <Alert type="info" showIcon message={source.notes.map(noteLabel).join(" ")} /> : null}
        </Space>
      ),
    }
  })

  return (
    <Card
      className="ai-usage-card"
      title={<Space><BarChartOutlined />{copy.title}</Space>}
      extra={<Segmented value={days} onChange={(value) => setDays(Number(value))} options={[7, 30, 90, 365].map((value) => ({ label: `${value}${locale === "ru" ? "д" : "d"}`, value }))} />}
      style={{ marginBottom: 16 }}
    >
      {analytics.isLoading ? <div className="ai-usage-loading"><Spin /></div> : analytics.isError || !analytics.data ? <Alert type="error" showIcon message={copy.unavailable} description={analytics.error?.message} /> : <>
        <Row gutter={[12, 12]} className="ai-usage-summary">
          <Col xs={12} md={8} xl={4}><Card size="small"><Statistic title={copy.requests} value={analytics.data.requests} /></Card></Col>
          <Col xs={12} md={8} xl={4}><Card size="small"><Statistic title={copy.success} value={analytics.data.successful_requests} /></Card></Col>
          <Col xs={12} md={8} xl={4}><Card size="small"><Statistic title={copy.failures} value={analytics.data.failed_requests} /></Card></Col>
          <Col xs={12} md={8} xl={4}><Card size="small"><Statistic title={copy.usersSum} value={analytics.data.unique_users_sum} /></Card></Col>
          <Col xs={12} md={8} xl={4}><Card size="small"><Statistic title={copy.tokens} value={analytics.data.total_tokens} formatter={(value) => number(Number(value))} /></Card></Col>
          <Col xs={12} md={8} xl={4}><Card size="small"><Statistic title={copy.totalCost} value={analytics.data.cost_usd === null ? "—" : `$${money(analytics.data.cost_usd)}`} /></Card></Col>
        </Row>
        <Typography.Text type="secondary" className="ai-usage-unique-note">{copy.uniqueNote}</Typography.Text>
        <Tabs items={tabs} />
        <Typography.Text type="secondary">{copy.updated}: {dateTime(analytics.data.generated_at, locale)}</Typography.Text>
      </>}
    </Card>
  )
}

function SupportInboxTab() {
  const { locale } = useLanguage()
  const { hasPermission, principal } = useAuth()
  const queryClient = useQueryClient()
  const [params, setParams] = useSearchParams()
  const [reply, setReply] = useState("")
  const [internal, setInternal] = useState(false)
  const [composeOpen, setComposeOpen] = useState(false)
  const [customerSearch, setCustomerSearch] = useState("")
  const [startForm] = Form.useForm<StartConversationForm>()
  const search = params.get("support_q") || ""
  const status = params.get("support_status") || "active"
  const selectedId = Number(params.get("conversation_id") || 0) || null
  const targetCustomerId = Number(params.get("customer_id") || 0) || null
  const copy = locale === "ru"
    ? {
      title: "Обращения",
      newConversation: "Написать клиенту",
      newConversationTitle: "Новое сообщение клиенту",
      chooseCustomer: "Клиент",
      customerSearch: "Найдите клиента по имени, телефону или email",
      subject: "Тема",
      subjectPlaceholder: "Например: персональная консультация",
      firstMessage: "Сообщение",
      firstMessagePlaceholder: "Напишите первое сообщение клиенту…",
      conversationStarted: "Сообщение отправлено",
      inactiveCustomer: "заблокирован",
      existingConversation: "есть активный чат",
      cancel: "Отмена",
      search: "Клиент или тема",
      all: "Все",
      active: "Активные",
      unread: "Непрочитанные",
      select: "Выберите обращение",
      noItems: "Обращений пока нет",
      reply: "Ответить клиенту",
      note: "Внутренняя заметка",
      send: "Отправить",
      customer: "Клиент",
      assignee: "Ответственный",
      priority: "Приоритет",
      status: "Статус",
      sla: "SLA",
      order: "Заказ",
      createLead: "Создать лид",
      createTask: "Создать задачу",
      read: "прочитано",
      delivered: "доставлено",
      leadCreated: "Лид создан",
      attachment: "Скачать вложение",
      sender: "Отправитель",
      replyBy: "Ответ от",
      noteBy: "Заметка от",
      system: "Система",
    }
    : {
      title: "Support inbox",
      newConversation: "Message customer",
      newConversationTitle: "New customer message",
      chooseCustomer: "Customer",
      customerSearch: "Find a customer by name, phone, or email",
      subject: "Subject",
      subjectPlaceholder: "For example: personal consultation",
      firstMessage: "Message",
      firstMessagePlaceholder: "Write the first message to the customer…",
      conversationStarted: "Message sent",
      inactiveCustomer: "blocked",
      existingConversation: "active chat exists",
      cancel: "Cancel",
      search: "Customer or subject",
      all: "All",
      active: "Active",
      unread: "Unread",
      select: "Select a conversation",
      noItems: "No support requests yet",
      reply: "Reply to customer",
      note: "Internal note",
      send: "Send",
      customer: "Customer",
      assignee: "Assignee",
      priority: "Priority",
      status: "Status",
      sla: "SLA",
      order: "Order",
      createLead: "Create lead",
      createTask: "Create task",
      read: "read",
      delivered: "delivered",
      leadCreated: "Lead created",
      attachment: "Download attachment",
      sender: "Sender",
      replyBy: "Reply by",
      noteBy: "Note by",
      system: "System",
    }
  const statusLabels: Record<SupportConversationStatus, string> = locale === "ru"
    ? { new: "Новое", open: "В работе", waiting_customer: "Ждём клиента", waiting_team: "Ждём команду", resolved: "Закрыто", spam: "Спам" }
    : { new: "New", open: "Open", waiting_customer: "Waiting customer", waiting_team: "Waiting team", resolved: "Resolved", spam: "Spam" }

  const updateParam = (key: string, value?: string | number) => {
    setParams((current) => {
      const next = new URLSearchParams(current)
      if (value === undefined || value === "") next.delete(key)
      else next.set(key, String(value))
      return next
    })
  }
  const openConversation = (conversationId: number) => {
    setParams((current) => {
      const next = new URLSearchParams(current)
      next.set("conversation_id", String(conversationId))
      next.delete("customer_id")
      next.delete("support_status")
      return next
    })
  }
  const closeComposer = () => {
    setComposeOpen(false)
    setCustomerSearch("")
    startForm.resetFields()
    if (targetCustomerId) updateParam("customer_id")
  }
  const listQuery = useQuery({
    queryKey: ["support-conversations", search, status],
    queryFn: () => apiRequest<Page<SupportConversation>>(`/support/conversations${queryString({
      q: search,
      status,
      limit: 100,
    })}`),
    refetchInterval: 5000,
  })
  const targetCustomerQuery = useQuery({
    queryKey: ["support-target-customer", targetCustomerId],
    queryFn: () => apiRequest<Page<SupportCustomer>>(`/support/customers${queryString({
      customer_user_id: targetCustomerId,
      limit: 1,
    })}`),
    enabled: Boolean(targetCustomerId),
  })
  const customerOptionsQuery = useQuery({
    queryKey: ["support-customer-options", customerSearch],
    queryFn: () => apiRequest<Page<SupportCustomer>>(`/support/customers${queryString({
      q: customerSearch.trim() || undefined,
      limit: 30,
    })}`),
    enabled: composeOpen,
  })
  const detailQuery = useQuery({
    queryKey: ["support-conversation", selectedId],
    queryFn: () => apiRequest<SupportConversationDetail>(`/support/conversations/${selectedId}`),
    enabled: Boolean(selectedId),
    refetchInterval: 5000,
  })
  const assignees = useQuery({
    queryKey: ["support-assignees"],
    queryFn: () => apiRequest<AssigneeOption[]>("/tasks/assignees"),
    enabled: hasPermission("support.assign"),
  })
  const selected = detailQuery.data
  const targetCustomer = targetCustomerQuery.data?.items[0]
  const customerOptions = useMemo(() => {
    const items = [...(customerOptionsQuery.data?.items || [])]
    if (targetCustomer && !items.some((item) => item.id === targetCustomer.id)) items.unshift(targetCustomer)
    return items
  }, [customerOptionsQuery.data?.items, targetCustomer])

  useEffect(() => {
    if (!selectedId || !selected?.admin_unread_count) return
    void apiRequest(`/support/conversations/${selectedId}/read`, { method: "POST" }).then(() => {
      void queryClient.invalidateQueries({ queryKey: ["support-conversations"] })
      void queryClient.invalidateQueries({ queryKey: ["support-conversation", selectedId] })
    })
  }, [queryClient, selected?.admin_unread_count, selectedId])

  useEffect(() => {
    if (!targetCustomerId || !targetCustomer) return
    if (targetCustomer.active_conversation_id) {
      openConversation(targetCustomer.active_conversation_id)
      return
    }
    setComposeOpen(true)
    startForm.setFieldsValue({ customer_user_id: targetCustomer.id })
  // The URL target is consumed by openConversation or closeComposer.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startForm, targetCustomer, targetCustomerId])

  const startConversationMutation = useMutation({
    mutationFn: (values: StartConversationForm) => apiRequest<SupportConversationDetail>("/support/conversations", {
      method: "POST",
      body: JSON.stringify({
        customer_user_id: values.customer_user_id,
        subject: values.subject?.trim() || null,
        body: values.body.trim(),
      }),
    }),
    onSuccess: (result) => {
      setComposeOpen(false)
      setCustomerSearch("")
      startForm.resetFields()
      queryClient.setQueryData(["support-conversation", result.id], result)
      void queryClient.invalidateQueries({ queryKey: ["support-conversations"] })
      void queryClient.invalidateQueries({ queryKey: ["support-customer-options"] })
      openConversation(result.id)
      void message.success(copy.conversationStarted)
    },
    onError: (error: Error) => void message.error(error.message),
  })

  const replyMutation = useMutation({
    mutationFn: () => apiRequest<SupportConversationDetail>(`/support/conversations/${selectedId}/messages`, {
      method: "POST",
      body: JSON.stringify({ body: reply.trim(), is_internal: internal }),
    }),
    onSuccess: (result) => {
      setReply("")
      setInternal(false)
      queryClient.setQueryData(["support-conversation", selectedId], result)
      void queryClient.invalidateQueries({ queryKey: ["support-conversations"] })
    },
    onError: (error: Error) => void message.error(error.message),
  })
  const updateMutation = useMutation({
    mutationFn: (values: Record<string, unknown>) => apiRequest<SupportConversationDetail>(`/support/conversations/${selectedId}`, {
      method: "PATCH",
      body: JSON.stringify({ ...values, expected_updated_at: selected?.updated_at }),
    }),
    onSuccess: (result) => {
      queryClient.setQueryData(["support-conversation", selectedId], result)
      void queryClient.invalidateQueries({ queryKey: ["support-conversations"] })
    },
    onError: (error: Error) => void message.error(error.message),
  })
  const createLead = useMutation({
    mutationFn: () => apiRequest("/leads", {
      method: "POST",
      body: JSON.stringify({
        title: selected?.subject || `${locale === "ru" ? "Обращение" : "Support request"} #${selectedId}`,
        source: "support",
        priority: selected?.priority || "normal",
        score: selected?.priority === "urgent" ? 80 : selected?.priority === "high" ? 60 : 30,
        conversation_id: selectedId,
        customer_user_id: selected?.customer_user_id,
        owner_user_id: selected?.assignee_user_id || principal?.user.id,
        description: selected?.messages.filter((item) => !item.is_internal).at(-1)?.body || null,
      }),
    }),
    onSuccess: () => void message.success(copy.leadCreated),
    onError: (error: Error) => void message.error(error.message),
  })

  return (
    <Row gutter={16} className="communications-grid">
      <Col xs={24} lg={8} xl={7}>
        <Card
          title={<Space><CustomerServiceOutlined />{copy.title}<Badge count={listQuery.data?.items.reduce((sum, item) => sum + item.admin_unread_count, 0) || 0} /></Space>}
          extra={hasPermission("support.reply") ? (
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => {
                startForm.resetFields()
                setCustomerSearch("")
                setComposeOpen(true)
              }}
            >
              {copy.newConversation}
            </Button>
          ) : null}
          className="communications-list-card"
        >
          <Space direction="vertical" style={{ width: "100%" }}>
            <Input allowClear prefix={<SearchOutlined />} placeholder={copy.search} value={search} onChange={(event) => updateParam("support_q", event.target.value)} />
            <Select
              value={status}
              style={{ width: "100%" }}
              onChange={(value) => updateParam("support_status", value === "active" ? undefined : value)}
              options={[
                { value: "active", label: copy.active },
                { value: "new", label: statusLabels.new },
                { value: "open", label: statusLabels.open },
                { value: "waiting_customer", label: statusLabels.waiting_customer },
                { value: "waiting_team", label: statusLabels.waiting_team },
                { value: "resolved", label: statusLabels.resolved },
                { value: "all", label: copy.all },
              ]}
            />
          </Space>
          <List
            loading={listQuery.isLoading}
            locale={{ emptyText: copy.noItems }}
            dataSource={listQuery.data?.items || []}
            renderItem={(item) => (
              <List.Item
                className={`conversation-list-item ${selectedId === item.id ? "conversation-list-item-active" : ""}`}
                onClick={() => updateParam("conversation_id", item.id)}
              >
                <List.Item.Meta
                  avatar={<Badge count={item.admin_unread_count} size="small"><Avatar>{item.customer_name.slice(0, 1)}</Avatar></Badge>}
                  title={<Space><Typography.Text strong ellipsis>{item.customer_name}</Typography.Text><Tag color={statusColors[item.status]}>{statusLabels[item.status]}</Tag></Space>}
                  description={<div className="table-primary"><span>{item.subject || `#${item.id}`}</span><small>{item.last_message_preview || item.customer_email || "—"}</small><small>{dateTime(item.last_message_at, locale)}</small></div>}
                />
              </List.Item>
            )}
          />
          <Modal
            open={composeOpen}
            title={copy.newConversationTitle}
            okText={copy.send}
            cancelText={copy.cancel}
            confirmLoading={startConversationMutation.isPending}
            onCancel={closeComposer}
            onOk={() => void startForm.validateFields().then((values) => startConversationMutation.mutate(values))}
          >
            <Form form={startForm} layout="vertical">
              <Form.Item
                name="customer_user_id"
                label={copy.chooseCustomer}
                rules={[{ required: true }]}
              >
                <Select
                  showSearch
                  filterOption={false}
                  loading={customerOptionsQuery.isFetching || targetCustomerQuery.isFetching}
                  placeholder={copy.customerSearch}
                  onSearch={setCustomerSearch}
                  onChange={(customerId: number) => {
                    const customer = customerOptions.find((item) => item.id === customerId)
                    if (!customer?.active_conversation_id) return
                    setComposeOpen(false)
                    setCustomerSearch("")
                    startForm.resetFields()
                    openConversation(customer.active_conversation_id)
                  }}
                  options={customerOptions.map((customer) => {
                    const customerName = `${customer.name} ${customer.surname}`.trim() || `#${customer.id}`
                    const details = [
                      customer.email || customer.phone_number,
                      !customer.is_active ? copy.inactiveCustomer : null,
                      customer.active_conversation_id ? copy.existingConversation : null,
                    ].filter(Boolean)
                    return {
                      value: customer.id,
                      label: `${customerName}${details.length ? ` · ${details.join(" · ")}` : ""}`,
                    }
                  })}
                />
              </Form.Item>
              <Form.Item name="subject" label={copy.subject}>
                <Input maxLength={240} placeholder={copy.subjectPlaceholder} />
              </Form.Item>
              <Form.Item
                name="body"
                label={copy.firstMessage}
                rules={[{ required: true, whitespace: true, min: 1, max: 8000 }]}
              >
                <Input.TextArea rows={5} maxLength={8000} showCount placeholder={copy.firstMessagePlaceholder} />
              </Form.Item>
            </Form>
          </Modal>
        </Card>
      </Col>
      <Col xs={24} lg={16} xl={17}>
        {!selectedId ? <Card className="communications-detail-card"><Empty description={copy.select} /></Card> : detailQuery.isLoading || !selected ? (
          <Card className="communications-detail-card"><Spin /></Card>
        ) : (
          <Card
            className="communications-detail-card"
            title={<Space><MessageOutlined /><Link to={`/customers/${selected.customer_user_id}`}>{selected.customer_name}</Link><Tag color={priorityColors[selected.priority]}>{domainLabel(selected.priority, locale)}</Tag>{selected.sla_breached_at ? <Tag color="red">SLA</Tag> : null}</Space>}
            extra={<Space>
              {hasPermission("leads.manage") ? <Button icon={<UserAddOutlined />} onClick={() => createLead.mutate()} loading={createLead.isPending}>{copy.createLead}</Button> : null}
              {hasPermission("tasks.manage") ? <Link to={`/tasks?new=1&customer_id=${selected.customer_user_id}`}><Button>{copy.createTask}</Button></Link> : null}
            </Space>}
          >
            <Descriptions size="small" column={{ xs: 1, md: 3 }} className="conversation-context">
              <Descriptions.Item label={copy.customer}><Link to={`/customers/${selected.customer_user_id}`}>{selected.customer_email || selected.customer_phone || `#${selected.customer_user_id}`}</Link></Descriptions.Item>
              <Descriptions.Item label={copy.status}>
                <Select
                  size="small"
                  disabled={!hasPermission("support.assign")}
                  value={selected.status}
                  onChange={(value) => updateMutation.mutate({ status: value })}
                  options={Object.entries(statusLabels).map(([value, label]) => ({ value, label }))}
                />
              </Descriptions.Item>
              <Descriptions.Item label={copy.priority}>
                <Select
                  size="small"
                  disabled={!hasPermission("support.assign")}
                  value={selected.priority}
                  onChange={(value) => updateMutation.mutate({ priority: value })}
                  options={(["low", "normal", "high", "urgent"] as const).map((value) => ({ value, label: domainLabel(value, locale) }))}
                />
              </Descriptions.Item>
              <Descriptions.Item label={copy.assignee}>
                <Select
                  allowClear
                  size="small"
                  disabled={!hasPermission("support.assign")}
                  value={selected.assignee_user_id || undefined}
                  onChange={(value) => updateMutation.mutate({ assignee_user_id: value || null })}
                  options={(assignees.data || []).map((item) => ({ value: item.user_id, label: item.name }))}
                  style={{ minWidth: 180 }}
                />
              </Descriptions.Item>
              <Descriptions.Item label={copy.sla}><ClockCircleOutlined /> {dateTime(selected.first_responded_at ? selected.resolution_due_at : selected.response_due_at, locale)}</Descriptions.Item>
              <Descriptions.Item label={copy.order}>{selected.order_id ? <Link to={`/sales/orders/${selected.order_id}`}>{selected.order_code || `#${selected.order_id}`}</Link> : "—"}</Descriptions.Item>
            </Descriptions>
            <div className="conversation-thread">
              {selected.messages.map((item) => (
                <div key={item.id} className={`admin-message-row ${item.sender_type === "admin" ? "admin-message-row-own" : ""}`}>
                  <div className={`admin-message-bubble ${item.is_internal ? "admin-message-internal" : ""}`}>
                    <strong className="admin-message-author">
                      {item.sender_type === "user"
                        ? `${copy.sender}: ${item.author_name}`
                        : item.sender_type === "admin"
                          ? `${item.is_internal ? copy.noteBy : copy.replyBy}: ${item.author_name}`
                          : copy.system}
                      {item.author_role ? <small> · {item.author_role}</small> : null}
                    </strong>
                    <span>{item.body}</span>
                    {item.attachments.map((attachment) => (
                      <Button
                        key={attachment.id}
                        size="small"
                        icon={<DownloadOutlined />}
                        onClick={() => void apiDownload(attachment.download_url.replace("/api/v1/admin", "")).then(({ blob, fileName }) => downloadBlob(blob, fileName || attachment.original_filename))}
                      >
                        {attachment.original_filename}
                      </Button>
                    ))}
                    <small>{dateTime(item.created_at, locale)}{item.sender_type === "admin" && !item.is_internal ? ` · ${item.read_at ? copy.read : copy.delivered}` : ""}</small>
                  </div>
                </div>
              ))}
            </div>
            {hasPermission("support.reply") && !["resolved", "spam"].includes(selected.status) ? (
              <div className="conversation-composer">
                <Input.TextArea rows={3} value={reply} onChange={(event) => setReply(event.target.value)} placeholder={internal ? copy.note : copy.reply} maxLength={8000} />
                <Space>
                  <Switch checked={internal} onChange={setInternal} /> <Typography.Text>{copy.note}</Typography.Text>
                  <Button type="primary" icon={<SendOutlined />} disabled={!reply.trim()} loading={replyMutation.isPending} onClick={() => replyMutation.mutate()}>{copy.send}</Button>
                </Space>
              </div>
            ) : null}
          </Card>
        )}
      </Col>
    </Row>
  )
}

function extractInteractive(context: Record<string, unknown>) {
  const interactive = context.interactive
  if (!interactive || typeof interactive !== "object" || Array.isArray(interactive)) return []
  const cards = (interactive as { cards?: unknown }).cards
  return Array.isArray(cards) ? cards as Array<Record<string, unknown>> : []
}

function AIChatsTab() {
  const { locale } = useLanguage()
  const { hasPermission, principal } = useAuth()
  const queryClient = useQueryClient()
  const [params, setParams] = useSearchParams()
  const search = params.get("ai_q") || ""
  const selectedId = Number(params.get("ai_chat_id") || 0) || null
  const [securitySource, setSecuritySource] = useState<AIChatSecuritySource>("app")
  const [suspiciousOnly, setSuspiciousOnly] = useState(false)
  const [banOpen, setBanOpen] = useState(false)
  const [banForm] = Form.useForm<{ ban_type: "account" | "ip"; subject: string; reason: string }>()
  const copy = locale === "ru"
    ? { title: "AI Chat", search: "Клиент или сообщение", select: "Выберите AI-диалог", noItems: "AI-диалогов пока нет", messages: "сообщений", tokens: "токенов", createLead: "Создать лид", leadCreated: "Лид создан", model: "Модель", actions: "Фактические действия пользователя", noActions: "Действий пока нет", completed: "выполнено", eventMessage: "Отправил сообщение", eventShown: "Получил рекомендацию", eventClicked: "Нажал действие", eventCompleted: "Выполнил действие", product: "товар", variant: "вариант" }
    : { title: "AI Chat", search: "Customer or message", select: "Select an AI conversation", noItems: "No AI conversations yet", messages: "messages", tokens: "tokens", createLead: "Create lead", leadCreated: "Lead created", model: "Model", actions: "Actual user actions", noActions: "No actions yet", completed: "completed", eventMessage: "Sent a message", eventShown: "Received a recommendation", eventClicked: "Clicked an action", eventCompleted: "Completed an action", product: "product", variant: "variant" }
  const eventLabels: Record<string, string> = {
    ai_chat_message_sent: copy.eventMessage,
    ai_recommendation_shown: copy.eventShown,
    ai_action_clicked: copy.eventClicked,
    ai_action_completed: copy.eventCompleted,
  }
  const updateParam = (key: string, value?: string | number) => setParams((current) => {
    const next = new URLSearchParams(current)
    if (value === undefined || value === "") next.delete(key)
    else next.set(key, String(value))
    return next
  })
  const list = useQuery({
    queryKey: ["ai-chats", search],
    queryFn: () => apiRequest<Page<AIChatListItem>>(`/ai-chats${queryString({ q: search, limit: 100 })}`),
  })
  const detail = useQuery({
    queryKey: ["ai-chat", selectedId],
    queryFn: () => apiRequest<AIChatDetail>(`/ai-chats/${selectedId}`),
    enabled: Boolean(selectedId),
  })
  const securityOverview = useQuery({
    queryKey: ["ai-security", "overview"],
    queryFn: () => apiRequest<AIChatSecurityOverview>("/ai-chats/security/overview"),
    refetchInterval: 30_000,
  })
  const securityEvents = useQuery({
    queryKey: ["ai-security", "activity", securitySource, suspiciousOnly],
    queryFn: () => apiRequest<Page<AIChatSecurityEvent>>(`/ai-chats/security/activity${queryString({ source: securitySource, suspicious_only: suspiciousOnly, limit: 100 })}`),
  })
  const securityBans = useQuery({
    queryKey: ["ai-security", "bans", securitySource],
    queryFn: () => apiRequest<Page<AIChatBan>>(`/ai-chats/security/bans${queryString({ source: securitySource })}`),
  })
  const createBan = useMutation({
    mutationFn: (values: { ban_type: "account" | "ip"; subject: string; reason: string }) => apiRequest<AIChatBan>("/ai-chats/security/bans", {
      method: "POST",
      body: JSON.stringify({ source: securitySource, ...values }),
    }),
    onSuccess: () => {
      setBanOpen(false)
      banForm.resetFields()
      void queryClient.invalidateQueries({ queryKey: ["ai-security"] })
      void message.success(locale === "ru" ? "Блокировка включена" : "Ban enabled")
    },
    onError: (error: Error) => void message.error(error.message),
  })
  const revokeBan = useMutation({
    mutationFn: (ban: AIChatBan) => apiRequest<AIChatBan>(`/ai-chats/security/bans/${ban.source}/${ban.id}/revoke`, { method: "POST" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["ai-security"] })
      void message.success(locale === "ru" ? "Блокировка снята" : "Ban revoked")
    },
    onError: (error: Error) => void message.error(error.message),
  })
  const createLead = useMutation({
    mutationFn: () => apiRequest("/leads", {
      method: "POST",
      body: JSON.stringify({
        title: `${locale === "ru" ? "Интерес из AI Chat" : "AI Chat opportunity"} #${selectedId}`,
        source: "ai_chat",
        priority: "normal",
        score: 45,
        customer_user_id: detail.data?.user_id,
        owner_user_id: principal?.user.id,
        description: detail.data?.messages.filter((item) => item.sender === "user").at(-1)?.text || null,
      }),
    }),
    onSuccess: () => void message.success(copy.leadCreated),
    onError: (error: Error) => void message.error(error.message),
  })

  const securityCopy = locale === "ru"
    ? { title: "Активность и защита AI-чатов", app: "Приложение", bitrix: "Bitrix-сайт", messages24: "Сообщений за 24 часа", suspicious: "Подозрительных", activeBans: "Активных блокировок", onlySuspicious: "Только подозрительные", activity: "Последняя активность", bans: "Блокировки", noActivity: "Активности пока нет", noBans: "Активных блокировок нет", ban: "Заблокировать", unban: "Снять", account: "Аккаунт", ip: "IP-адрес", reason: "Причина", subject: "ID аккаунта или IP", unavailable: "Источник не подключён или временно недоступен" }
    : { title: "AI chat activity and security", app: "Application", bitrix: "Bitrix website", messages24: "Messages in 24 hours", suspicious: "Suspicious", activeBans: "Active bans", onlySuspicious: "Suspicious only", activity: "Recent activity", bans: "Bans", noActivity: "No activity yet", noBans: "No active bans", ban: "Ban", unban: "Revoke", account: "Account", ip: "IP address", reason: "Reason", subject: "Account ID or IP", unavailable: "Source is not configured or temporarily unavailable" }
  const riskLabel = (reason: string) => ({
    high_message_rate_minute: locale === "ru" ? "частые сообщения за минуту" : "high message rate per minute",
    high_message_rate_hour: locale === "ru" ? "частые сообщения за час" : "high message rate per hour",
    many_accounts_same_ip: locale === "ru" ? "много аккаунтов с одного IP" : "many accounts from one IP",
    active_account_ban: locale === "ru" ? "блокировка аккаунта" : "account ban",
    active_ip_ban: locale === "ru" ? "блокировка IP" : "IP ban",
  }[reason] || reason)
  const openBan = (banType: "account" | "ip", subject?: string | null) => {
    banForm.setFieldsValue({ ban_type: banType, subject: subject || "", reason: "" })
    setBanOpen(true)
  }

  return (<>
    <AIUsageAnalyticsCard />
    <Card title={<Space><RobotOutlined />{securityCopy.title}</Space>} style={{ marginBottom: 16 }}>
      <Row gutter={[12, 12]}>
        {(["app", "bitrix"] as const).map((source) => {
          const item = securityOverview.data?.[source]
          return (
            <Col xs={24} md={12} key={source}>
              <Card size="small" type="inner" title={source === "app" ? securityCopy.app : securityCopy.bitrix}>
                {item?.error || item?.configured === false ? <Typography.Text type="danger">{securityCopy.unavailable}</Typography.Text> : (
                  <Space wrap>
                    <Tag color="blue">{securityCopy.messages24}: {item?.messages ?? "—"}</Tag>
                    <Tag color={(item?.suspicious || 0) > 0 ? "red" : "green"}>{securityCopy.suspicious}: {item?.suspicious ?? "—"}</Tag>
                    <Tag color={(item?.active_bans || 0) > 0 ? "orange" : "default"}>{securityCopy.activeBans}: {item?.active_bans ?? "—"}</Tag>
                  </Space>
                )}
              </Card>
            </Col>
          )
        })}
      </Row>
      <Space wrap style={{ margin: "16px 0" }}>
        <Select<AIChatSecuritySource>
          value={securitySource}
          onChange={setSecuritySource}
          options={[{ value: "app", label: securityCopy.app }, { value: "bitrix", label: securityCopy.bitrix }]}
          style={{ width: 180 }}
        />
        <Switch checked={suspiciousOnly} onChange={setSuspiciousOnly} />
        <Typography.Text>{securityCopy.onlySuspicious}</Typography.Text>
        {hasPermission("ai_chats.manage") ? <Button danger onClick={() => openBan("account")}>{securityCopy.ban}</Button> : null}
      </Space>
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={16}>
          <Card size="small" title={securityCopy.activity}>
            <List
              loading={securityEvents.isLoading}
              locale={{ emptyText: securityCopy.noActivity }}
              dataSource={securityEvents.data?.items || []}
              renderItem={(item) => (
                <List.Item actions={hasPermission("ai_chats.manage") ? [
                  <Button key="account" size="small" danger onClick={() => openBan("account", item.account_id)}>{securityCopy.account}</Button>,
                  <Button key="ip" size="small" danger disabled={!item.ip_address} onClick={() => openBan("ip", item.ip_address)}>{securityCopy.ip}</Button>,
                ] : undefined}>
                  <List.Item.Meta
                    avatar={<Badge status={item.is_suspicious ? "error" : "success"} />}
                    title={<Space wrap><Typography.Text strong>{item.display_name || item.email_address || `#${item.account_id}`}</Typography.Text><Tag>{item.event_type}</Tag>{item.is_suspicious ? <Tag color="red">Risk {item.risk_score}</Tag> : null}</Space>}
                    description={<div className="table-primary"><span>{item.ip_address || "—"} · {dateTime(item.created_at, locale)}</span>{item.risk_reasons.length ? <small>{item.risk_reasons.map(riskLabel).join(", ")}</small> : null}</div>}
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>
        <Col xs={24} xl={8}>
          <Card size="small" title={securityCopy.bans}>
            <List
              loading={securityBans.isLoading}
              locale={{ emptyText: securityCopy.noBans }}
              dataSource={securityBans.data?.items || []}
              renderItem={(item) => (
                <List.Item actions={hasPermission("ai_chats.manage") ? [<Button key="revoke" size="small" onClick={() => revokeBan.mutate(item)}>{securityCopy.unban}</Button>] : undefined}>
                  <List.Item.Meta title={<Space><Tag color="red">{item.ban_type === "ip" ? securityCopy.ip : securityCopy.account}</Tag>{item.subject}</Space>} description={item.reason} />
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>
    </Card>
    <Modal
      title={securityCopy.ban}
      open={banOpen}
      okText={securityCopy.ban}
      okButtonProps={{ danger: true, loading: createBan.isPending }}
      onCancel={() => setBanOpen(false)}
      onOk={() => void banForm.validateFields().then((values) => createBan.mutate(values))}
    >
      <Form form={banForm} layout="vertical" requiredMark={false}>
        <Form.Item name="ban_type" label={locale === "ru" ? "Тип" : "Type"} rules={[{ required: true }]}><Select options={[{ value: "account", label: securityCopy.account }, { value: "ip", label: securityCopy.ip }]} /></Form.Item>
        <Form.Item name="subject" label={securityCopy.subject} rules={[{ required: true, min: 1, max: 254 }]}><Input /></Form.Item>
        <Form.Item name="reason" label={securityCopy.reason} rules={[{ required: true, min: 3, max: 2000 }]}><Input.TextArea rows={3} /></Form.Item>
      </Form>
    </Modal>
    <Row gutter={16} className="communications-grid">
      <Col xs={24} lg={8} xl={7}>
        <Card title={<Space><RobotOutlined />{copy.title}</Space>} className="communications-list-card">
          <Input allowClear prefix={<SearchOutlined />} placeholder={copy.search} value={search} onChange={(event) => updateParam("ai_q", event.target.value)} />
          <List
            loading={list.isLoading}
            locale={{ emptyText: copy.noItems }}
            dataSource={list.data?.items || []}
            renderItem={(item) => (
              <List.Item className={`conversation-list-item ${selectedId === item.id ? "conversation-list-item-active" : ""}`} onClick={() => updateParam("ai_chat_id", item.id)}>
                <List.Item.Meta
                  avatar={<Avatar icon={<RobotOutlined />} />}
                  title={item.customer_name}
                  description={<div className="table-primary"><span>{item.last_message || "—"}</span><small>{item.messages_count} {copy.messages} · {item.total_tokens} {copy.tokens}</small><small>{dateTime(item.last_activity_at, locale)}</small></div>}
                />
              </List.Item>
            )}
          />
        </Card>
      </Col>
      <Col xs={24} lg={16} xl={17}>
        {!selectedId ? <Card className="communications-detail-card"><Empty description={copy.select} /></Card> : detail.isLoading || !detail.data ? (
          <Card className="communications-detail-card"><Spin /></Card>
        ) : (
          <Card
            className="communications-detail-card"
            title={<Space><RobotOutlined /><Link to={`/customers/${detail.data.user_id}`}>{detail.data.customer_name}</Link><Tag>{detail.data.total_tokens} {copy.tokens}</Tag></Space>}
            extra={hasPermission("leads.manage") ? <Button icon={<UserAddOutlined />} loading={createLead.isPending} onClick={() => createLead.mutate()}>{copy.createLead}</Button> : null}
          >
            <Card size="small" title={copy.actions} className="ai-actions-card">
              {detail.data.actions.length ? (
                <Timeline
                  items={detail.data.actions.map((action) => ({
                    color: action.event_name === "ai_action_completed" ? "green" : action.event_name === "ai_action_clicked" ? "blue" : "gray",
                    children: (
                      <div>
                        <Space wrap>
                          <Typography.Text strong>{eventLabels[action.event_name] || domainLabel(action.event_name, locale)}</Typography.Text>
                          {action.action_type ? <Tag color="blue">{domainLabel(action.action_type, locale)}</Tag> : null}
                          {action.product_id ? hasPermission("catalog.read") ? <Link to={`/catalog/products?product_id=${action.product_id}`}><Tag className="navigation-tag">{copy.product} #{action.product_id}</Tag></Link> : <Tag>{copy.product} #{action.product_id}</Tag> : null}
                          {action.variant_id ? <Tag>{copy.variant} #{action.variant_id}</Tag> : null}
                          <Typography.Text type="secondary">{dateTime(action.occurred_at, locale)}</Typography.Text>
                        </Space>
                      </div>
                    ),
                  }))}
                />
              ) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={copy.noActions} />}
            </Card>
            <Timeline
              items={detail.data.messages.map((item) => {
                const cards = extractInteractive(item.context)
                return {
                  color: item.sender === "user" ? "blue" : "green",
                  children: (
                    <div className={`ai-audit-message ${item.sender === "user" ? "ai-audit-user" : ""}`}>
                      <Space><Tag color={item.sender === "user" ? "blue" : "green"}>{domainLabel(item.sender, locale)}</Tag><Typography.Text type="secondary">{dateTime(item.created_at, locale)}</Typography.Text>{item.usage ? <Tag>{copy.model}: {item.usage.openai_model}</Tag> : null}</Space>
                      <Typography.Paragraph style={{ whiteSpace: "pre-wrap", marginTop: 8 }}>{item.text}</Typography.Paragraph>
                      {item.attachments.length ? (
                        <Space wrap>
                          {item.attachments.map((attachment) => (
                            <Button
                              key={attachment.id}
                              size="small"
                              icon={<DownloadOutlined />}
                              onClick={() => void apiDownload(attachment.url.replace("/api/v1/admin", "")).then(({ blob, fileName }) => downloadBlob(blob, fileName || attachment.name))}
                            >
                              {attachment.name}
                            </Button>
                          ))}
                        </Space>
                      ) : null}
                      {cards.map((card, cardIndex) => {
                        const actions = Array.isArray(card.actions) ? card.actions as Array<Record<string, unknown>> : []
                        return (
                          <Card key={`${item.id}-${cardIndex}`} size="small" title={card.product_id && hasPermission("catalog.read") ? <Link className="section-navigation-link" to={`/catalog/products?product_id=${String(card.product_id)}`}>{String(card.title || `${copy.product} ${card.product_id}`)}</Link> : String(card.title || `${copy.product} ${card.product_id || ""}`)}>
                            <Space wrap>
                              {actions.map((action, actionIndex) => <Tag key={String(action.id || actionIndex)} color={action.completed ? "green" : "default"}>{domainLabel(String(action.type || "action"), locale)}{action.completed ? ` · ${copy.completed}` : ""}</Tag>)}
                            </Space>
                          </Card>
                        )
                      })}
                    </div>
                  ),
                }
              })}
            />
          </Card>
        )}
      </Col>
    </Row>
  </>)
}

export function CommunicationsPage() {
  const { locale } = useLanguage()
  const { hasPermission } = useAuth()
  const [params, setParams] = useSearchParams()
  const requestedTab = params.get("tab")
  const activeTab = requestedTab === "ai" ? "ai" : "support"
  const tabs = useMemo(() => [
    hasPermission("support.read") ? { key: "support", label: locale === "ru" ? "Поддержка" : "Support", children: <SupportInboxTab /> } : null,
    hasPermission("ai_chats.read") ? { key: "ai", label: "AI Chat", children: <AIChatsTab /> } : null,
  ].filter(Boolean) as Array<{ key: string; label: string; children: React.ReactNode }>, [hasPermission, locale])
  const resolvedTab = tabs.some((item) => item.key === activeTab) ? activeTab : tabs[0]?.key
  return (
    <div className="page-stack">
      <PageHeader title={locale === "ru" ? "Коммуникации" : "Communications"} description={locale === "ru" ? "Поддержка пользователей и наблюдение за AI Chat" : "Customer support and AI Chat visibility"} />
      <Card>
        <Tabs
          activeKey={resolvedTab}
          items={tabs}
          onChange={(key) => setParams((current) => {
            const next = new URLSearchParams(current)
            if (key === "support") next.delete("tab")
            else next.set("tab", key)
            return next
          })}
        />
      </Card>
    </div>
  )
}
