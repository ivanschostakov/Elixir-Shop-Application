import {
  ClockCircleOutlined,
  CustomerServiceOutlined,
  DownloadOutlined,
  MessageOutlined,
  RobotOutlined,
  SearchOutlined,
  SendOutlined,
  UserAddOutlined,
} from "@ant-design/icons"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  Avatar,
  Badge,
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  Input,
  List,
  Row,
  Select,
  Space,
  Spin,
  Switch,
  Tabs,
  Tag,
  Timeline,
  Typography,
  message,
} from "antd"
import { useEffect, useMemo, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { apiDownload, apiRequest, queryString } from "../api/client"
import type {
  AIChatDetail,
  AIChatListItem,
  AssigneeOption,
  Page,
  SupportConversation,
  SupportConversationDetail,
  SupportConversationStatus,
} from "../api/types"
import { PageHeader } from "../components/PageHeader"
import { useAuth } from "../auth/AuthProvider"
import { useLanguage } from "../i18n/LanguageProvider"
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

function downloadBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = fileName
  anchor.click()
  URL.revokeObjectURL(url)
}

function SupportInboxTab() {
  const { locale } = useLanguage()
  const { hasPermission, principal } = useAuth()
  const queryClient = useQueryClient()
  const [params, setParams] = useSearchParams()
  const [reply, setReply] = useState("")
  const [internal, setInternal] = useState(false)
  const search = params.get("support_q") || ""
  const status = params.get("support_status") || "active"
  const selectedId = Number(params.get("conversation_id") || 0) || null
  const copy = locale === "ru"
    ? {
      title: "Обращения",
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
    }
    : {
      title: "Support inbox",
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
  const listQuery = useQuery({
    queryKey: ["support-conversations", search, status],
    queryFn: () => apiRequest<Page<SupportConversation>>(`/support/conversations${queryString({
      q: search,
      status,
      limit: 100,
    })}`),
    refetchInterval: 5000,
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

  useEffect(() => {
    if (!selectedId || !selected?.admin_unread_count) return
    void apiRequest(`/support/conversations/${selectedId}/read`, { method: "POST" }).then(() => {
      void queryClient.invalidateQueries({ queryKey: ["support-conversations"] })
      void queryClient.invalidateQueries({ queryKey: ["support-conversation", selectedId] })
    })
  }, [queryClient, selected?.admin_unread_count, selectedId])

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
        </Card>
      </Col>
      <Col xs={24} lg={16} xl={17}>
        {!selectedId ? <Card className="communications-detail-card"><Empty description={copy.select} /></Card> : detailQuery.isLoading || !selected ? (
          <Card className="communications-detail-card"><Spin /></Card>
        ) : (
          <Card
            className="communications-detail-card"
            title={<Space><MessageOutlined /><Link to={`/customers/${selected.customer_user_id}`}>{selected.customer_name}</Link><Tag color={priorityColors[selected.priority]}>{selected.priority}</Tag>{selected.sla_breached_at ? <Tag color="red">SLA</Tag> : null}</Space>}
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
                  options={(["low", "normal", "high", "urgent"] as const).map((value) => ({ value, label: value }))}
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
                    <strong>{item.author_name}{item.author_role ? ` · ${item.author_role}` : ""}</strong>
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
  const [params, setParams] = useSearchParams()
  const search = params.get("ai_q") || ""
  const selectedId = Number(params.get("ai_chat_id") || 0) || null
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

  return (
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
                          <Typography.Text strong>{eventLabels[action.event_name] || action.event_name}</Typography.Text>
                          {action.action_type ? <Tag color="blue">{action.action_type}</Tag> : null}
                          {action.product_id ? <Tag>{copy.product} #{action.product_id}</Tag> : null}
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
                      <Space><Tag color={item.sender === "user" ? "blue" : "green"}>{item.sender}</Tag><Typography.Text type="secondary">{dateTime(item.created_at, locale)}</Typography.Text>{item.usage ? <Tag>{copy.model}: {item.usage.openai_model}</Tag> : null}</Space>
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
                          <Card key={`${item.id}-${cardIndex}`} size="small" title={String(card.title || `Product ${card.product_id || ""}`)}>
                            <Space wrap>
                              {actions.map((action, actionIndex) => <Tag key={String(action.id || actionIndex)} color={action.completed ? "green" : "default"}>{String(action.type || "action")}{action.completed ? ` · ${copy.completed}` : ""}</Tag>)}
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
  )
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
