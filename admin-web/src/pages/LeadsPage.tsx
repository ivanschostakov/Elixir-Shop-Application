import { PlusOutlined, SearchOutlined, UserAddOutlined } from "@ant-design/icons"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  Button,
  Card,
  DatePicker,
  Drawer,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Timeline,
  Typography,
  message,
} from "antd"
import dayjs, { type Dayjs } from "dayjs"
import { useEffect, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { apiRequest, queryString } from "../api/client"
import type { AssigneeOption, CrmLead, CrmLeadDetail, LeadStatus, Page } from "../api/types"
import { useAuth } from "../auth/AuthProvider"
import { PageHeader } from "../components/PageHeader"
import { useLanguage } from "../i18n/LanguageProvider"
import { dateTime } from "../utils/format"

type LeadForm = {
  title: string
  source?: "manual" | "support" | "ai_chat" | "customer_intelligence"
  status?: LeadStatus
  priority: CrmLead["priority"]
  score: number
  customer_user_id?: number
  conversation_id?: number
  product_id?: number
  category_id?: number
  owner_user_id?: number
  converted_order_id?: number
  contact_name?: string
  contact_email?: string
  contact_phone?: string
  description?: string
  next_action_at?: Dayjs
  lost_reason?: string
  stage_reason?: string
}

const statusColors: Record<LeadStatus, string> = { new: "blue", contacted: "cyan", interested: "purple", waiting: "gold", converted: "green", lost: "red" }
const priorityColors = { low: "default", normal: "blue", high: "orange", urgent: "red" } as const

export function LeadsPage() {
  const { locale } = useLanguage()
  const { hasPermission, principal } = useAuth()
  const queryClient = useQueryClient()
  const [params, setParams] = useSearchParams()
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [editing, setEditing] = useState<CrmLeadDetail | null>(null)
  const [note, setNote] = useState("")
  const [form] = Form.useForm<LeadForm>()
  const watchedStatus = Form.useWatch("status", form)
  const search = params.get("q") || ""
  const status = params.get("status") || "active"
  const priority = params.get("priority") || "all"
  const owner = params.get("owner") || "all"
  const page = Math.max(Number(params.get("page") || 1) || 1, 1)
  const pageSize = 50
  const copy = locale === "ru"
    ? {
      title: "Лиды",
      description: "Коммерческие возможности до создания заказа",
      create: "Новый лид",
      search: "Лид, клиент или контакт",
      active: "Активные",
      all: "Все",
      mine: "Мои",
      titleField: "Название",
      customer: "Клиент",
      source: "Источник",
      stage: "Этап",
      priority: "Приоритет",
      score: "Score",
      owner: "Ответственный",
      nextAction: "Следующее действие",
      context: "Контекст",
      save: "Сохранить",
      descriptionField: "Описание",
      conversation: "Обращение",
      product: "ID товара",
      category: "ID категории",
      convertedOrder: "ID заказа",
      lostReason: "Причина потери",
      stageReason: "Комментарий к смене этапа",
      history: "История этапов",
      notes: "Заметки",
      addNote: "Добавить заметку",
      contact: "Контакты",
      saved: "Лид сохранён",
    }
    : {
      title: "Leads",
      description: "Commercial opportunities before an order exists",
      create: "New lead",
      search: "Lead, customer or contact",
      active: "Active",
      all: "All",
      mine: "Mine",
      titleField: "Title",
      customer: "Customer",
      source: "Source",
      stage: "Stage",
      priority: "Priority",
      score: "Score",
      owner: "Owner",
      nextAction: "Next action",
      context: "Context",
      save: "Save",
      descriptionField: "Description",
      conversation: "Conversation",
      product: "Product ID",
      category: "Category ID",
      convertedOrder: "Order ID",
      lostReason: "Lost reason",
      stageReason: "Stage change note",
      history: "Stage history",
      notes: "Notes",
      addNote: "Add note",
      contact: "Contacts",
      saved: "Lead saved",
    }
  const statusLabels: Record<LeadStatus, string> = locale === "ru"
    ? { new: "Новый", contacted: "Связались", interested: "Интерес", waiting: "Ожидание", converted: "Конвертирован", lost: "Потерян" }
    : { new: "New", contacted: "Contacted", interested: "Interested", waiting: "Waiting", converted: "Converted", lost: "Lost" }
  const updateFilter = (values: Record<string, string | number | undefined>) => setParams((current) => {
    const next = new URLSearchParams(current)
    Object.entries(values).forEach(([key, value]) => {
      if (
        value === undefined
        || value === ""
        || value === 1
        || (value === "all" && key !== "status")
        || (key === "status" && value === "active")
      ) next.delete(key)
      else next.set(key, String(value))
    })
    return next
  })
  const list = useQuery({
    queryKey: ["leads", search, status, priority, owner, page],
    queryFn: () => apiRequest<Page<CrmLead>>(`/leads${queryString({
      q: search,
      status,
      priority: priority === "all" ? undefined : priority,
      owner_user_id: owner === "mine" ? principal?.user.id : undefined,
      limit: pageSize,
      offset: (page - 1) * pageSize,
    })}`),
  })
  const assignees = useQuery({
    queryKey: ["lead-assignees"],
    queryFn: () => apiRequest<AssigneeOption[]>("/tasks/assignees"),
  })

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({ source: "manual", status: "new", priority: "normal", score: 0, owner_user_id: principal?.user.id })
    setDrawerOpen(true)
  }
  const openEdit = async (lead: CrmLead) => {
    const detail = await apiRequest<CrmLeadDetail>(`/leads/${lead.id}`)
    setEditing(detail)
    form.setFieldsValue({
      title: detail.title,
      source: detail.source as LeadForm["source"],
      status: detail.status,
      priority: detail.priority,
      score: detail.score,
      customer_user_id: detail.customer_user_id || undefined,
      conversation_id: detail.conversation_id || undefined,
      product_id: detail.product_id || undefined,
      category_id: detail.category_id || undefined,
      owner_user_id: detail.owner_user_id || undefined,
      converted_order_id: detail.converted_order_id || undefined,
      contact_name: detail.contact_name || undefined,
      contact_email: detail.contact_email || undefined,
      contact_phone: detail.contact_phone || undefined,
      description: detail.description || undefined,
      next_action_at: detail.next_action_at ? dayjs(detail.next_action_at) : undefined,
      lost_reason: detail.lost_reason || undefined,
    })
    setDrawerOpen(true)
  }
  useEffect(() => {
    if (params.get("new") === "1") {
      openCreate()
      updateFilter({ new: undefined })
    }
    // URL-controlled opening only reacts to the explicit flag.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.get("new")])

  const save = useMutation({
    mutationFn: (values: LeadForm) => {
      const shared = {
        title: values.title.trim(),
        priority: values.priority,
        score: values.score,
        owner_user_id: values.owner_user_id || null,
        product_id: values.product_id || null,
        category_id: values.category_id || null,
        description: values.description?.trim() || null,
        next_action_at: values.next_action_at?.toISOString() || null,
      }
      const body = editing ? {
        ...shared,
        status: values.status,
        converted_order_id: values.converted_order_id || null,
        lost_reason: values.lost_reason?.trim() || null,
        stage_reason: values.stage_reason?.trim() || null,
        expected_updated_at: editing.updated_at,
      } : {
        ...shared,
        source: values.source || "manual",
        customer_user_id: values.customer_user_id || null,
        conversation_id: values.conversation_id || null,
        contact_name: values.contact_name?.trim() || null,
        contact_email: values.contact_email?.trim() || null,
        contact_phone: values.contact_phone?.trim() || null,
      }
      return apiRequest<CrmLeadDetail>(editing ? `/leads/${editing.id}` : "/leads", {
        method: editing ? "PATCH" : "POST",
        body: JSON.stringify(body),
      })
    },
    onSuccess: (result) => {
      setEditing(result)
      setDrawerOpen(false)
      void queryClient.invalidateQueries({ queryKey: ["leads"] })
      void message.success(copy.saved)
    },
    onError: (error: Error) => void message.error(error.message),
  })
  const addNote = useMutation({
    mutationFn: () => apiRequest<CrmLeadDetail>(`/leads/${editing?.id}/notes`, { method: "POST", body: JSON.stringify({ body: note.trim() }) }),
    onSuccess: (result) => {
      setEditing(result)
      setNote("")
      void queryClient.invalidateQueries({ queryKey: ["leads"] })
    },
    onError: (error: Error) => void message.error(error.message),
  })

  return (
    <div className="page-stack">
      <PageHeader title={copy.title} description={copy.description} actions={hasPermission("leads.manage") ? <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>{copy.create}</Button> : null} />
      <Card className="filter-card"><Space wrap>
        <Input allowClear prefix={<SearchOutlined />} placeholder={copy.search} value={search} onChange={(event) => updateFilter({ q: event.target.value, page: 1 })} />
        <Select value={status} style={{ width: 170 }} onChange={(value) => updateFilter({ status: value, page: 1 })} options={[{ value: "active", label: copy.active }, { value: "all", label: copy.all }, ...Object.entries(statusLabels).map(([value, label]) => ({ value, label }))]} />
        <Select value={priority} style={{ width: 150 }} onChange={(value) => updateFilter({ priority: value, page: 1 })} options={[{ value: "all", label: copy.all }, ...(["low", "normal", "high", "urgent"] as const).map((value) => ({ value, label: value }))]} />
        <Select value={owner} style={{ width: 150 }} onChange={(value) => updateFilter({ owner: value, page: 1 })} options={[{ value: "all", label: copy.all }, { value: "mine", label: copy.mine }]} />
      </Space></Card>
      <Table<CrmLead>
        rowKey="id"
        loading={list.isLoading}
        dataSource={list.data?.items}
        pagination={{ current: page, pageSize, total: list.data?.total, showSizeChanger: false, onChange: (next) => updateFilter({ page: next }) }}
        onRow={(lead) => ({ onClick: () => void openEdit(lead), style: { cursor: "pointer" } })}
        columns={[
          { title: copy.titleField, key: "lead", render: (_: unknown, lead) => <div className="table-primary"><strong>{lead.title}</strong><small>#{lead.id} · {lead.source}</small></div> },
          { title: copy.customer, key: "customer", render: (_: unknown, lead) => lead.customer_user_id ? <Link onClick={(event) => event.stopPropagation()} to={`/customers/${lead.customer_user_id}`}>{lead.customer_name || `#${lead.customer_user_id}`}</Link> : lead.contact_name || "—" },
          { title: copy.context, key: "context", render: (_: unknown, lead) => <Space direction="vertical" size={0}>{lead.conversation_id ? <Link onClick={(event) => event.stopPropagation()} to={`/communications?conversation_id=${lead.conversation_id}`}>{copy.conversation} #{lead.conversation_id}</Link> : null}{lead.converted_order_id ? <Link onClick={(event) => event.stopPropagation()} to={`/sales/orders/${lead.converted_order_id}`}>{lead.converted_order_code || `#${lead.converted_order_id}`}</Link> : null}{lead.product_name || lead.category_name || "—"}</Space> },
          { title: copy.owner, dataIndex: "owner_name", render: (value: string | null) => value || "—" },
          { title: copy.score, dataIndex: "score", render: (value: number) => <Tag color={value >= 70 ? "red" : value >= 40 ? "orange" : "blue"}>{value}</Tag> },
          { title: copy.priority, dataIndex: "priority", render: (value: CrmLead["priority"]) => <Tag color={priorityColors[value]}>{value}</Tag> },
          { title: copy.nextAction, dataIndex: "next_action_at", render: (value: string | null) => dateTime(value, locale) },
          { title: copy.stage, dataIndex: "status", render: (value: LeadStatus) => <Tag color={statusColors[value]}>{statusLabels[value]}</Tag> },
        ]}
      />
      <Drawer
        open={drawerOpen}
        width={640}
        title={<Space><UserAddOutlined />{editing ? `${copy.titleField} #${editing.id}` : copy.create}</Space>}
        onClose={() => setDrawerOpen(false)}
        extra={hasPermission("leads.manage") ? <Button type="primary" loading={save.isPending} onClick={() => void form.validateFields().then((values) => save.mutate(values))}>{copy.save}</Button> : null}
      >
        <Form form={form} layout="vertical" disabled={!hasPermission("leads.manage")}>
          <Form.Item name="title" label={copy.titleField} rules={[{ required: true, min: 1, max: 240 }]}><Input /></Form.Item>
          <Space align="start" wrap>
            {!editing ? <Form.Item name="source" label={copy.source}><Select style={{ width: 170 }} options={["manual", "support", "ai_chat", "customer_intelligence"].map((value) => ({ value, label: value }))} /></Form.Item> : null}
            {editing ? <Form.Item name="status" label={copy.stage}><Select style={{ width: 170 }} options={Object.entries(statusLabels).map(([value, label]) => ({ value, label }))} /></Form.Item> : null}
            <Form.Item name="priority" label={copy.priority}><Select style={{ width: 140 }} options={["low", "normal", "high", "urgent"].map((value) => ({ value, label: value }))} /></Form.Item>
            <Form.Item name="score" label={copy.score}><InputNumber min={0} max={100} /></Form.Item>
          </Space>
          <Space align="start" wrap>
            <Form.Item name="customer_user_id" label="Customer ID"><InputNumber min={1} disabled={Boolean(editing)} /></Form.Item>
            <Form.Item name="conversation_id" label={copy.conversation}><InputNumber min={1} disabled={Boolean(editing)} /></Form.Item>
            <Form.Item name="owner_user_id" label={copy.owner}><Select allowClear style={{ width: 210 }} options={(assignees.data || []).map((item) => ({ value: item.user_id, label: item.name }))} /></Form.Item>
          </Space>
          <Space align="start" wrap>
            <Form.Item name="product_id" label={copy.product}><InputNumber min={1} /></Form.Item>
            <Form.Item name="category_id" label={copy.category}><InputNumber min={1} /></Form.Item>
            <Form.Item name="next_action_at" label={copy.nextAction}><DatePicker showTime /></Form.Item>
          </Space>
          {!editing ? <Space align="start" wrap>
            <Form.Item name="contact_name" label={copy.contact}><Input /></Form.Item>
            <Form.Item name="contact_email" label="Email"><Input type="email" /></Form.Item>
            <Form.Item name="contact_phone" label="Phone"><Input /></Form.Item>
          </Space> : null}
          {watchedStatus === "converted" ? <Form.Item name="converted_order_id" label={copy.convertedOrder} rules={[{ required: true }]}><InputNumber min={1} /></Form.Item> : null}
          {watchedStatus === "lost" ? <Form.Item name="lost_reason" label={copy.lostReason} rules={[{ required: true, min: 1 }]}><Input.TextArea rows={2} /></Form.Item> : null}
          {editing ? <Form.Item name="stage_reason" label={copy.stageReason}><Input /></Form.Item> : null}
          <Form.Item name="description" label={copy.descriptionField}><Input.TextArea rows={5} maxLength={8000} /></Form.Item>
        </Form>
        {editing ? (
          <Tabs items={[
            {
              key: "history",
              label: copy.history,
              children: <Timeline items={editing.stage_history.map((item) => ({ color: statusColors[item.to_status as LeadStatus] || "blue", children: <div><strong>{item.from_status ? `${item.from_status} → ` : ""}{item.to_status}</strong><div>{item.changed_by_name || "—"} · {dateTime(item.created_at, locale)}</div>{item.reason ? <Typography.Text type="secondary">{item.reason}</Typography.Text> : null}</div> }))} />,
            },
            {
              key: "notes",
              label: copy.notes,
              children: <Space direction="vertical" style={{ width: "100%" }}><Input.TextArea rows={3} value={note} onChange={(event) => setNote(event.target.value)} /><Button disabled={!note.trim()} loading={addNote.isPending} onClick={() => addNote.mutate()}>{copy.addNote}</Button>{editing.notes.map((item) => <Card key={item.id} size="small"><Typography.Paragraph>{item.body}</Typography.Paragraph><Typography.Text type="secondary">{item.author_name || "—"} · {dateTime(item.created_at, locale)}</Typography.Text></Card>)}</Space>,
            },
          ]} />
        ) : null}
      </Drawer>
    </div>
  )
}
