import { CheckOutlined, ClockCircleOutlined, PlusOutlined, SearchOutlined } from "@ant-design/icons"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Button, Card, DatePicker, Drawer, Form, Input, InputNumber, Select, Space, Table, Tag, Typography, message } from "antd"
import dayjs, { type Dayjs } from "dayjs"
import { useEffect, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { apiRequest, queryString } from "../api/client"
import type { AdminTask, AssigneeOption, Page } from "../api/types"
import { useAuth } from "../auth/AuthProvider"
import { PageHeader } from "../components/PageHeader"
import { useLanguage } from "../i18n/LanguageProvider"
import { dateTime } from "../utils/format"

type TaskForm = {
  title: string
  description?: string
  status?: AdminTask["status"]
  priority: AdminTask["priority"]
  due_at?: Dayjs
  customer_user_id?: number
  order_id?: number
  assignee_user_id?: number
}

const priorityColors: Record<AdminTask["priority"], string> = { low: "default", normal: "blue", high: "orange", urgent: "red" }
const statusColors: Record<AdminTask["status"], string> = { open: "blue", in_progress: "gold", done: "green", canceled: "default" }

export function TasksPage() {
  const { locale } = useLanguage()
  const { principal, hasPermission } = useAuth()
  const client = useQueryClient()
  const [params, setParams] = useSearchParams()
  const [editing, setEditing] = useState<AdminTask | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [form] = Form.useForm<TaskForm>()
  const search = params.get("q") || ""
  const status = params.get("status") || "active"
  const assignee = params.get("assignee") || "all"
  const overdue = params.get("overdue") === "true"
  const slaBreached = params.get("sla_breached") === "true"
  const customerId = Number(params.get("customer_id") || 0) || undefined
  const page = Math.max(Number(params.get("page") || 1) || 1, 1)
  const pageSize = 50
  const updateFilters = (values: Record<string, string | number | undefined>) => {
    setParams((current) => {
      const next = new URLSearchParams(current)
      Object.entries(values).forEach(([key, value]) => {
        if (value === undefined || value === "" || value === 1 || value === "all" || (key === "status" && value === "active")) next.delete(key)
        else next.set(key, String(value))
      })
      return next
    })
  }
  const query = useQuery({
    queryKey: ["tasks", search, status, assignee, overdue, slaBreached, customerId, page],
    queryFn: () => apiRequest<Page<AdminTask>>(`/tasks${queryString({
      q: search,
      status,
      assignee_user_id: assignee === "mine" ? principal?.user.id : undefined,
      customer_user_id: customerId,
      overdue: overdue || undefined,
      sla_breached: slaBreached || undefined,
      limit: pageSize,
      offset: (page - 1) * pageSize,
    })}`),
  })
  const assignees = useQuery({ queryKey: ["task-assignees"], queryFn: () => apiRequest<AssigneeOption[]>("/tasks/assignees") })
  const copy = locale === "ru"
    ? { title: "Задачи", description: "Работа команды по клиентам и заказам", create: "Новая задача", search: "Название или описание", active: "Активные", all: "Все статусы", open: "Новая", progress: "В работе", done: "Выполнена", canceled: "Отменена", allAssignees: "Все сотрудники", mine: "Мои задачи", overdue: "Просроченные", slaBreached: "Нарушен SLA", sla: "SLA", task: "Задача", context: "Контекст", assignee: "Ответственный", priority: "Приоритет", due: "Срок", status: "Статус", edit: "Редактировать", save: "Сохранить", descriptionField: "Описание", customerId: "ID клиента", orderId: "ID заказа", noDue: "Без срока", completed: "Задача выполнена" }
    : { title: "Tasks", description: "Team work linked to customers and orders", create: "New task", search: "Title or description", active: "Active", all: "All statuses", open: "Open", progress: "In progress", done: "Done", canceled: "Canceled", allAssignees: "All staff", mine: "My tasks", overdue: "Overdue", slaBreached: "SLA breached", sla: "SLA", task: "Task", context: "Context", assignee: "Assignee", priority: "Priority", due: "Due", status: "Status", edit: "Edit", save: "Save", descriptionField: "Description", customerId: "Customer ID", orderId: "Order ID", noDue: "No due date", completed: "Task completed" }
  const statusLabels: Record<AdminTask["status"], string> = { open: copy.open, in_progress: copy.progress, done: copy.done, canceled: copy.canceled }

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({ priority: "normal", status: "open", assignee_user_id: principal?.user.id, customer_user_id: customerId })
    setDrawerOpen(true)
  }
  const openEdit = (task: AdminTask) => {
    setEditing(task)
    form.setFieldsValue({
      title: task.title,
      description: task.description || undefined,
      status: task.status,
      priority: task.priority,
      due_at: task.due_at ? dayjs(task.due_at) : undefined,
      customer_user_id: task.customer_user_id || undefined,
      order_id: task.order_id || undefined,
      assignee_user_id: task.assignee_user_id,
    })
    setDrawerOpen(true)
  }
  useEffect(() => {
    if (params.get("new") === "1") {
      openCreate()
      updateFilters({ new: undefined })
    }
    // Open-on-arrival is intentionally handled only when the URL flag changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.get("new")])

  const save = useMutation({
    mutationFn: (values: TaskForm) => apiRequest<AdminTask>(editing ? `/tasks/${editing.id}` : "/tasks", {
      method: editing ? "PATCH" : "POST",
      body: JSON.stringify({
        ...values,
        due_at: values.due_at?.toISOString() || null,
        description: values.description?.trim() || null,
        ...(editing ? { expected_updated_at: editing.updated_at } : {}),
      }),
    }),
    onSuccess: () => {
      setDrawerOpen(false)
      void client.invalidateQueries({ queryKey: ["tasks"] })
      void message.success(locale === "ru" ? "Задача сохранена" : "Task saved")
    },
    onError: (error: Error) => void message.error(error.message),
  })
  const complete = useMutation({
    mutationFn: (task: AdminTask) => apiRequest<AdminTask>(`/tasks/${task.id}`, { method: "PATCH", body: JSON.stringify({ status: "done", expected_updated_at: task.updated_at }) }),
    onSuccess: () => { void client.invalidateQueries({ queryKey: ["tasks"] }); void message.success(copy.completed) },
    onError: (error: Error) => void message.error(error.message),
  })

  return <div className="page-stack">
    <PageHeader title={copy.title} description={copy.description} actions={hasPermission("tasks.manage") ? <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>{copy.create}</Button> : null} />
    <Card className="filter-card"><Space wrap>
      <Input allowClear prefix={<SearchOutlined />} placeholder={copy.search} value={search} onChange={(event) => updateFilters({ q: event.target.value, page: 1 })} />
      <Select value={status} style={{ width: 165 }} onChange={(value) => updateFilters({ status: value, page: 1 })} options={[{ value: "active", label: copy.active }, { value: "all", label: copy.all }, { value: "open", label: copy.open }, { value: "in_progress", label: copy.progress }, { value: "done", label: copy.done }, { value: "canceled", label: copy.canceled }]} />
      <Select value={assignee} style={{ width: 170 }} onChange={(value) => updateFilters({ assignee: value, page: 1 })} options={[{ value: "all", label: copy.allAssignees }, { value: "mine", label: copy.mine }]} />
      <Button type={overdue ? "primary" : "default"} icon={<ClockCircleOutlined />} onClick={() => updateFilters({ overdue: overdue ? undefined : "true", page: 1 })}>{copy.overdue}</Button>
      <Button danger={slaBreached} type={slaBreached ? "primary" : "default"} onClick={() => updateFilters({ sla_breached: slaBreached ? undefined : "true", page: 1 })}>{copy.slaBreached}</Button>
    </Space></Card>
    <Table<AdminTask>
      rowKey="id"
      loading={query.isLoading}
      dataSource={query.data?.items}
      pagination={{ current: page, pageSize, total: query.data?.total, showSizeChanger: false, onChange: (next) => updateFilters({ page: next }) }}
      onRow={(task) => ({ onDoubleClick: () => hasPermission("tasks.manage") && openEdit(task) })}
      columns={[
        { title: copy.task, key: "task", render: (_: unknown, task) => <div className="table-primary"><strong>{task.title}</strong><small>{task.description || `ID ${task.id}`}</small></div> },
        { title: copy.context, key: "context", render: (_: unknown, task) => <Space direction="vertical" size={0}>{task.customer_user_id ? <Link to={`/customers/${task.customer_user_id}`}>{task.customer_name || `#${task.customer_user_id}`}</Link> : "—"}{task.order_id ? <Link to={`/sales/orders/${task.order_id}`}>{task.order_code || `#${task.order_id}`}</Link> : null}</Space> },
        { title: copy.assignee, dataIndex: "assignee_name" },
        { title: copy.priority, dataIndex: "priority", render: (value: AdminTask["priority"]) => <Tag color={priorityColors[value]}>{value}</Tag> },
        { title: copy.due, dataIndex: "due_at", render: (value: string | null) => value ? dateTime(value, locale) : <Typography.Text type="secondary">{copy.noDue}</Typography.Text> },
        { title: copy.sla, render: (_: unknown, task) => task.sla_breached_at ? <Tag color="red">{copy.slaBreached}</Tag> : <Typography.Text type="secondary">{dateTime(task.status === "open" ? task.response_due_at : task.resolution_due_at, locale)}</Typography.Text> },
        { title: copy.status, dataIndex: "status", render: (value: AdminTask["status"]) => <Tag color={statusColors[value]}>{statusLabels[value]}</Tag> },
        { title: "", key: "actions", align: "right", render: (_: unknown, task) => hasPermission("tasks.manage") ? <Space><Button size="small" onClick={() => openEdit(task)}>{copy.edit}</Button>{!["done", "canceled"].includes(task.status) ? <Button size="small" type="text" icon={<CheckOutlined />} loading={complete.isPending} onClick={() => complete.mutate(task)} /> : null}</Space> : null },
      ]}
    />
    <Drawer width={520} open={drawerOpen} title={editing ? copy.edit : copy.create} onClose={() => setDrawerOpen(false)} extra={<Button type="primary" loading={save.isPending} onClick={() => void form.validateFields().then((values) => save.mutate(values))}>{copy.save}</Button>}>
      <Form form={form} layout="vertical" requiredMark={false}>
        <Form.Item name="title" label={copy.task} rules={[{ required: true, min: 1, max: 240 }]}><Input /></Form.Item>
        <Form.Item name="description" label={copy.descriptionField}><Input.TextArea rows={5} maxLength={4000} /></Form.Item>
        {editing ? <Form.Item name="status" label={copy.status}><Select options={Object.entries(statusLabels).map(([value, label]) => ({ value, label }))} /></Form.Item> : null}
        <Form.Item name="priority" label={copy.priority} rules={[{ required: true }]}><Select options={(["low", "normal", "high", "urgent"] as const).map((value) => ({ value, label: value }))} /></Form.Item>
        <Form.Item name="assignee_user_id" label={copy.assignee}><Select options={(assignees.data || []).map((item) => ({ value: item.user_id, label: item.name }))} /></Form.Item>
        <Form.Item name="due_at" label={copy.due}><DatePicker showTime style={{ width: "100%" }} /></Form.Item>
        <Space size={12} style={{ width: "100%" }} align="start">
          <Form.Item name="customer_user_id" label={copy.customerId}><InputNumber min={1} /></Form.Item>
          <Form.Item name="order_id" label={copy.orderId}><InputNumber min={1} /></Form.Item>
        </Space>
      </Form>
    </Drawer>
  </div>
}
