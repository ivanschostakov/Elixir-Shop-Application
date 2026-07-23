import {
  AlertOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  DeleteOutlined,
  EditOutlined,
  HistoryOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ProfileOutlined,
  RobotOutlined,
} from "@ant-design/icons"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Col,
  Drawer,
  Form,
  Input,
  InputNumber,
  message,
  Popconfirm,
  Progress,
  Row,
  Select,
  Space,
  Statistic,
  Switch,
  Table,
  Tabs,
  Tag,
  Typography,
} from "antd"
import { useMemo, useState, type ReactNode } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { apiRequest, queryString } from "../api/client"
import type {
  AdminAlert,
  AlertPage,
  AssigneeOption,
  IntegrationRun,
  OrderAutomationExecution,
  OrderAutomationPreset,
  OrderAutomationPresetApplyResponse,
  OrderAutomationPreview,
  OrderAutomationRule,
  OrderStatusCode,
  Page,
  SlaPolicy,
  SlaSummary,
} from "../api/types"
import { useAuth } from "../auth/AuthProvider"
import { PageHeader } from "../components/PageHeader"
import { useLanguage } from "../i18n/LanguageProvider"
import { dateTime } from "../utils/format"

const statusCodes: OrderStatusCode[] = ["created", "invoice_sent", "paid", "waiting_response", "packaged", "sent", "delivered", "completed", "canceled", "refund_declined"]
const priorityColors: Record<string, string> = { urgent: "red", high: "orange", normal: "blue", low: "default" }
const executionColors: Record<string, string> = { success: "green", queued: "blue", running: "blue", skipped: "default", error: "red" }

export function automationRulePayload(values: Record<string, unknown>, editingRule: OrderAutomationRule | null) {
  return {
    name: values.name,
    description: values.description || null,
    priority: values.priority,
    is_enabled: editingRule ? Boolean(values.is_enabled) : false,
    conditions_json: {
      status_codes: values.status_codes || [],
      payment_statuses: values.payment_statuses || [],
      min_age_minutes: values.min_age_minutes,
      missing_delivery: Boolean(values.missing_delivery),
      missing_moysklad: Boolean(values.missing_moysklad),
      only_active: Boolean(values.only_active),
    },
    action_json: values.action_kind === "create_task" ? {
      kind: "create_task", assignee_user_id: values.assignee_user_id, title: values.task_title, description: values.task_description || null, priority: values.task_priority, due_minutes: values.due_minutes,
    } : values.action_kind === "queue_operation" ? {
      kind: "queue_operation", operation: values.operation,
    } : {
      kind: "push_customer", title: values.push_title, body: values.push_body, deep_link: values.deep_link || null,
    },
    ...(editingRule ? { expected_updated_at: editingRule.updated_at } : {}),
  }
}

export function AutomationPage() {
  const { locale } = useLanguage()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const [params, setParams] = useSearchParams()
  const [ruleDrawer, setRuleDrawer] = useState(false)
  const [editingRule, setEditingRule] = useState<OrderAutomationRule | null>(null)
  const [historyRule, setHistoryRule] = useState<OrderAutomationRule | null>(null)
  const [previewRule, setPreviewRule] = useState<OrderAutomationRule | null>(null)
  const [policyDrawer, setPolicyDrawer] = useState(false)
  const [editingPolicy, setEditingPolicy] = useState<SlaPolicy | null>(null)
  const [ruleForm] = Form.useForm()
  const [policyForm] = Form.useForm()
  const tab = params.get("tab") || (hasPermission("automation.read") ? "rules" : hasPermission("sla.read") ? "sla" : "alerts")
  const actionKind = Form.useWatch("action_kind", ruleForm)
  const copy = locale === "ru" ? {
    title: "Автоматизация", description: "Правила заказов, SLA команды и операционные сбои", rules: "Правила заказов", sla: "SLA команды", alerts: "Сбои", newRule: "Новое правило", editRule: "Изменить правило", save: "Сохранить", name: "Название", descriptionField: "Описание", order: "Порядок", enabled: "Включено", disabled: "Выключено", conditions: "Условия", action: "Действие", minAge: "Возраст заказа, мин.", statuses: "Статусы заказа", payments: "Статусы оплаты", missingDelivery: "Доставка не создана", missingMoysklad: "Не выгружен в МойСклад", onlyActive: "Только активные заказы", createTask: "Создать задачу", queueOperation: "Запустить восстановление", pushCustomer: "Отправить push клиенту", assignee: "Ответственный", taskTitle: "Название задачи", taskPriority: "Приоритет задачи", dueMinutes: "Срок задачи, мин.", operation: "Операция", pushTitle: "Заголовок push", pushBody: "Текст push", deepLink: "Путь в приложении", lastRun: "Последний запуск", matches: "Совпадений", executions: "Запуски", run: "Запустить сейчас", runConfirm: "Проверить заказы и выполнить правило сейчас?", enableConfirm: "После включения правило будет автоматически выполнять действия. Продолжить?", delete: "Удалить", history: "История", createdDisabled: "Новое правило всегда создаётся выключенным. Проверьте условия перед включением.", response: "Ответ", resolution: "Решение", minutes: "мин.", compliance: "Соблюдение", openTasks: "Открыто", breached: "Нарушено", completed: "Завершено за 30 дней", edit: "Изменить", policiesHint: "Новые значения применяются к новым задачам и при смене приоритета.", source: "Источник", occurred: "Когда", incidents: "Активные сбои", read: "Прочитано", resolve: "Закрыть", open: "Открыть", noErrors: "Нет активных сбоев", automationQueued: "Запуск поставлен в очередь", ruleSaved: "Правило сохранено", policySaved: "SLA сохранён", presets: "Пресеты", applyPresets: "Создать пресеты", preview: "Предпросмотр", presetsApplied: "Пресеты созданы", customer: "Клиент",
  } : {
    title: "Automation", description: "Order rules, team SLA and operational failures", rules: "Order rules", sla: "Team SLA", alerts: "Failures", newRule: "New rule", editRule: "Edit rule", save: "Save", name: "Name", descriptionField: "Description", order: "Order", enabled: "Enabled", disabled: "Disabled", conditions: "Conditions", action: "Action", minAge: "Order age, min", statuses: "Order statuses", payments: "Payment statuses", missingDelivery: "Delivery is missing", missingMoysklad: "Missing in MoySklad", onlyActive: "Active orders only", createTask: "Create task", queueOperation: "Run recovery", pushCustomer: "Send customer push", assignee: "Assignee", taskTitle: "Task title", taskPriority: "Task priority", dueMinutes: "Task due, min", operation: "Operation", pushTitle: "Push title", pushBody: "Push body", deepLink: "App path", lastRun: "Last run", matches: "Matches", executions: "Runs", run: "Run now", runConfirm: "Check orders and execute this rule now?", enableConfirm: "Once enabled, this rule will perform actions automatically. Continue?", delete: "Delete", history: "History", createdDisabled: "New rules are always created disabled. Review the conditions before enabling.", response: "Response", resolution: "Resolution", minutes: "min", compliance: "Compliance", openTasks: "Open", breached: "Breached", completed: "Completed in 30 days", edit: "Edit", policiesHint: "New values apply to new tasks and when priority changes.", source: "Source", occurred: "Occurred", incidents: "Active failures", read: "Read", resolve: "Resolve", open: "Open", noErrors: "No active failures", automationQueued: "Automation run queued", ruleSaved: "Rule saved", policySaved: "SLA saved", presets: "Presets", applyPresets: "Create presets", preview: "Preview", presetsApplied: "Presets created", customer: "Customer",
  }

  const rules = useQuery({
    queryKey: ["order-automation-rules"],
    queryFn: () => apiRequest<Page<OrderAutomationRule>>("/order-automation-rules?limit=200"),
    enabled: hasPermission("automation.read"),
    refetchInterval: 30_000,
  })
  const assignees = useQuery({
    queryKey: ["task-assignees"],
    queryFn: () => apiRequest<AssigneeOption[]>("/tasks/assignees"),
    enabled: hasPermission("automation.manage"),
  })
  const presets = useQuery({
    queryKey: ["order-automation-presets"],
    queryFn: () => apiRequest<OrderAutomationPreset[]>("/order-automation-rules/presets"),
    enabled: hasPermission("automation.read"),
  })
  const policies = useQuery({
    queryKey: ["sla-policies"],
    queryFn: () => apiRequest<SlaPolicy[]>("/sla-policies"),
    enabled: hasPermission("sla.read"),
  })
  const slaSummary = useQuery({
    queryKey: ["sla-summary"],
    queryFn: () => apiRequest<SlaSummary[]>("/sla-summary"),
    enabled: hasPermission("sla.read"),
    refetchInterval: 60_000,
  })
  const alerts = useQuery({
    queryKey: ["admin-alerts"],
    queryFn: () => apiRequest<AlertPage>("/alerts?limit=200"),
    enabled: hasPermission("alerts.read"),
    refetchInterval: 30_000,
  })
  const executions = useQuery({
    queryKey: ["order-automation-executions", historyRule?.id],
    queryFn: () => apiRequest<Page<OrderAutomationExecution>>(`/order-automation-rules/${historyRule?.id}/executions?limit=100`),
    enabled: Boolean(historyRule),
  })
  const preview = useQuery({
    queryKey: ["order-automation-preview", previewRule?.id],
    queryFn: () => apiRequest<OrderAutomationPreview>(`/order-automation-rules/${previewRule?.id}/preview`),
    enabled: Boolean(previewRule),
  })

  const invalidateRules = () => queryClient.invalidateQueries({ queryKey: ["order-automation-rules"] })
  const saveRule = useMutation({
    mutationFn: async (values: Record<string, unknown>) => {
      const payload = automationRulePayload(values, editingRule)
      return apiRequest<OrderAutomationRule>(editingRule ? `/order-automation-rules/${editingRule.id}` : "/order-automation-rules", { method: editingRule ? "PUT" : "POST", body: JSON.stringify(payload) })
    },
    onSuccess: () => { message.success(copy.ruleSaved); setRuleDrawer(false); void invalidateRules() },
  })
  const updateRuleEnabled = useMutation({
    mutationFn: ({ rule, enabled }: { rule: OrderAutomationRule; enabled: boolean }) => apiRequest<OrderAutomationRule>(`/order-automation-rules/${rule.id}`, {
      method: "PUT",
      body: JSON.stringify({ name: rule.name, description: rule.description, priority: rule.priority, is_enabled: enabled, conditions_json: rule.conditions_json, action_json: rule.action_json, expected_updated_at: rule.updated_at }),
    }),
    onSuccess: () => void invalidateRules(),
  })
  const deleteRule = useMutation({
    mutationFn: (rule: OrderAutomationRule) => apiRequest<void>(`/order-automation-rules/${rule.id}`, { method: "DELETE" }),
    onSuccess: () => void invalidateRules(),
  })
  const applyPresets = useMutation({
    mutationFn: () => apiRequest<OrderAutomationPresetApplyResponse>("/order-automation-rules/presets/apply", { method: "POST" }),
    onSuccess: () => {
      message.success(copy.presetsApplied)
      void invalidateRules()
      void queryClient.invalidateQueries({ queryKey: ["order-automation-presets"] })
    },
  })
  const runRule = useMutation({
    mutationFn: (rule: OrderAutomationRule) => apiRequest<IntegrationRun>(`/order-automation-rules/${rule.id}/run`, { method: "POST", body: JSON.stringify({ expected_updated_at: rule.updated_at, idempotency_key: `automation-${rule.id}-${crypto.randomUUID()}` }) }),
    onSuccess: () => { message.success(copy.automationQueued); void invalidateRules() },
  })
  const savePolicy = useMutation({
    mutationFn: (values: Record<string, unknown>) => apiRequest<SlaPolicy>(`/sla-policies/${editingPolicy?.id}`, { method: "PUT", body: JSON.stringify({ ...values, expected_updated_at: editingPolicy?.updated_at }) }),
    onSuccess: () => { message.success(copy.policySaved); setPolicyDrawer(false); void queryClient.invalidateQueries({ queryKey: ["sla-policies"] }) },
  })
  const markRead = useMutation({
    mutationFn: (alert: AdminAlert) => apiRequest<AdminAlert>(`/alerts/${alert.id}/read`, { method: "POST" }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["admin-alerts"] }),
  })
  const resolveAlert = useMutation({
    mutationFn: (alert: AdminAlert) => apiRequest<AdminAlert>(`/alerts/${alert.id}/resolve`, { method: "POST" }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["admin-alerts"] }),
  })

  const openRule = (rule?: OrderAutomationRule) => {
    setEditingRule(rule || null)
    const conditions = rule?.conditions_json || {}
    const action = rule?.action_json || {}
    ruleForm.setFieldsValue({
      name: rule?.name, description: rule?.description, priority: rule?.priority ?? 100, is_enabled: rule?.is_enabled ?? false,
      status_codes: conditions.status_codes || [], payment_statuses: conditions.payment_statuses || [], min_age_minutes: conditions.min_age_minutes ?? 60,
      missing_delivery: conditions.missing_delivery ?? false, missing_moysklad: conditions.missing_moysklad ?? false, only_active: conditions.only_active ?? true,
      action_kind: action.kind || "create_task", assignee_user_id: action.assignee_user_id, task_title: action.title || "Заказ {order_code} требует внимания", task_description: action.description,
      task_priority: action.priority || "normal", due_minutes: action.due_minutes ?? 240, operation: action.operation || "payment_check", push_title: action.title, push_body: action.body, deep_link: action.deep_link,
    })
    setRuleDrawer(true)
  }
  const openPolicy = (policy: SlaPolicy) => {
    setEditingPolicy(policy)
    policyForm.setFieldsValue({ response_minutes: policy.response_minutes, resolution_minutes: policy.resolution_minutes, is_enabled: policy.is_enabled })
    setPolicyDrawer(true)
  }
  const conditionText = (rule: OrderAutomationRule) => {
    const value = rule.conditions_json
    const chunks = [`≥ ${value.min_age_minutes || 60} min`]
    if (value.status_codes?.length) chunks.push(value.status_codes.join(", "))
    if (value.payment_statuses?.length) chunks.push(value.payment_statuses.join(", "))
    if (value.missing_delivery) chunks.push(copy.missingDelivery)
    if (value.missing_moysklad) chunks.push(copy.missingMoysklad)
    return chunks.join(" · ")
  }
  const actionText = (rule: OrderAutomationRule) => {
    const kind = rule.action_json.kind
    if (kind === "create_task") return copy.createTask
    if (kind === "queue_operation") return `${copy.queueOperation}: ${String(rule.action_json.operation || "")}`
    return copy.pushCustomer
  }
  const overallCompliance = useMemo(() => {
    const completed = (slaSummary.data || []).reduce((sum, row) => sum + row.completed_30d, 0)
    const onTime = (slaSummary.data || []).reduce((sum, row) => sum + row.on_time_30d, 0)
    return completed ? Math.round(onTime / completed * 100) : 100
  }, [slaSummary.data])

  return <div className="page-stack">
    <PageHeader title={copy.title} description={copy.description} actions={tab === "rules" && hasPermission("automation.manage") ? <Space><Button icon={<ProfileOutlined />} loading={applyPresets.isPending} onClick={() => applyPresets.mutate()}>{copy.applyPresets}</Button><Button type="primary" icon={<PlusOutlined />} onClick={() => openRule()}>{copy.newRule}</Button></Space> : null} />
    <Tabs activeKey={tab} onChange={(value) => setParams({ tab: value })} items={[
      hasPermission("automation.read") ? { key: "rules", label: <Space><RobotOutlined />{copy.rules}</Space> } : null,
      hasPermission("sla.read") ? { key: "sla", label: <Space><ClockCircleOutlined />{copy.sla}</Space> } : null,
      hasPermission("alerts.read") ? { key: "alerts", label: <Space><AlertOutlined />{copy.alerts}{alerts.data?.unread_count ? <Tag color="red">{alerts.data.unread_count}</Tag> : null}</Space> } : null,
    ].filter(Boolean) as Array<{ key: string; label: ReactNode }>} />

    {tab === "rules" ? <div className="page-stack compact-stack">
      {presets.data?.length ? <Card size="small" title={copy.presets}><Space wrap>{presets.data.map((preset) => <Tag key={preset.code} color={preset.exists ? "green" : "default"}>{locale === "ru" ? preset.name_ru : preset.name_en}</Tag>)}</Space></Card> : null}
      <Table<OrderAutomationRule> rowKey="id" loading={rules.isLoading} dataSource={rules.data?.items} pagination={false} columns={[
      { title: copy.enabled, width: 90, render: (_: unknown, row) => row.is_enabled ? <Popconfirm title={copy.disabled} onConfirm={() => updateRuleEnabled.mutate({ rule: row, enabled: false })}><Switch checked /></Popconfirm> : hasPermission("automation.manage") ? <Popconfirm title={copy.enableConfirm} onConfirm={() => updateRuleEnabled.mutate({ rule: row, enabled: true })}><Switch checked={false} /></Popconfirm> : <Switch checked={false} disabled /> },
      { title: copy.name, render: (_: unknown, row) => <div className="table-primary"><strong>{row.name}</strong><small>{row.description || `#${row.priority}`}</small></div> },
      { title: copy.conditions, render: (_: unknown, row) => <Typography.Text type="secondary">{conditionText(row)}</Typography.Text> },
      { title: copy.action, render: (_: unknown, row) => <Tag>{actionText(row)}</Tag> },
      { title: copy.lastRun, render: (_: unknown, row) => <div className="table-primary"><span>{dateTime(row.last_run_at, locale)}</span><small>{copy.matches}: {row.last_match_count}</small></div> },
      { title: "", align: "right", render: (_: unknown, row) => <Space>{row.last_error ? <Tag color="red">Error</Tag> : null}<Button size="small" onClick={() => setPreviewRule(row)}>{copy.preview}</Button><Button size="small" icon={<HistoryOutlined />} onClick={() => setHistoryRule(row)}>{row.executions_count}</Button>{hasPermission("automation.manage") ? <><Popconfirm title={copy.runConfirm} onConfirm={() => runRule.mutate(row)}><Button size="small" icon={<PlayCircleOutlined />} loading={runRule.isPending}>{copy.run}</Button></Popconfirm><Button size="small" icon={<EditOutlined />} onClick={() => openRule(row)}>{copy.edit}</Button>{!row.is_enabled ? <Popconfirm title={copy.delete} onConfirm={() => deleteRule.mutate(row)}><Button size="small" danger type="text" icon={<DeleteOutlined />} /></Popconfirm> : null}</> : null}</Space> },
    ]} />
    </div> : null}

    {tab === "sla" ? <div className="page-stack compact-stack">
      <Alert type="info" showIcon message={copy.policiesHint} />
      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}><Card><Statistic title={copy.compliance} value={overallCompliance} suffix="%" prefix={<CheckCircleOutlined />} /></Card></Col>
        <Col xs={24} md={8}><Card><Statistic title={copy.openTasks} value={(slaSummary.data || []).reduce((sum, row) => sum + row.open_tasks, 0)} /></Card></Col>
        <Col xs={24} md={8}><Card><Statistic title={copy.breached} value={(slaSummary.data || []).reduce((sum, row) => sum + row.breached_tasks, 0)} valueStyle={{ color: "#dc2626" }} /></Card></Col>
      </Row>
      <Table<SlaPolicy> rowKey="id" loading={policies.isLoading} dataSource={policies.data} pagination={false} columns={[
        { title: copy.taskPriority, render: (_: unknown, row) => <Tag color={priorityColors[row.priority]}>{locale === "ru" ? row.name_ru : row.name_en}</Tag> },
        { title: copy.response, dataIndex: "response_minutes", render: (value: number) => `${value} ${copy.minutes}` },
        { title: copy.resolution, dataIndex: "resolution_minutes", render: (value: number) => `${value} ${copy.minutes}` },
        { title: copy.enabled, dataIndex: "is_enabled", render: (value: boolean) => <Tag color={value ? "green" : "default"}>{value ? copy.enabled : copy.disabled}</Tag> },
        { title: "", align: "right", render: (_: unknown, row) => hasPermission("sla.manage") ? <Button size="small" icon={<EditOutlined />} onClick={() => openPolicy(row)}>{copy.edit}</Button> : null },
      ]} />
      <Table<SlaSummary> rowKey="assignee_user_id" loading={slaSummary.isLoading} dataSource={slaSummary.data} pagination={false} columns={[
        { title: copy.assignee, dataIndex: "assignee_name" },
        { title: copy.openTasks, dataIndex: "open_tasks", align: "right" },
        { title: copy.breached, dataIndex: "breached_tasks", align: "right", render: (value: number) => <Tag color={value ? "red" : "green"}>{value}</Tag> },
        { title: copy.completed, dataIndex: "completed_30d", align: "right" },
        { title: copy.compliance, dataIndex: "compliance_percent", render: (value: string) => <Progress percent={Number(value)} size="small" status={Number(value) < 80 ? "exception" : "normal"} /> },
      ]} />
    </div> : null}

    {tab === "alerts" ? <Card title={`${copy.incidents} · ${alerts.data?.total || 0}`}><Table<AdminAlert> rowKey="id" loading={alerts.isLoading} dataSource={alerts.data?.items} locale={{ emptyText: copy.noErrors }} pagination={false} rowClassName={(row) => row.is_read ? "" : "unread-row"} columns={[
      { title: "", width: 48, render: (_: unknown, row) => <span className={`alert-dot alert-dot-${row.severity}`} /> },
      { title: copy.source, dataIndex: "source", render: (value: string) => <Tag>{value}</Tag> },
      { title: copy.name, render: (_: unknown, row) => <div className="table-primary"><strong>{locale === "ru" ? row.title_ru : row.title_en}</strong><small>{row.message}</small></div> },
      { title: copy.occurred, render: (_: unknown, row) => <div className="table-primary"><span>{dateTime(row.last_occurred_at, locale)}</span><small>× {row.occurrence_count}</small></div> },
      { title: "", align: "right", render: (_: unknown, row) => <Space>{!row.is_read ? <Button size="small" type="text" onClick={() => markRead.mutate(row)}>{copy.read}</Button> : null}{row.path ? <Link to={row.path}><Button size="small">{copy.open}</Button></Link> : null}{hasPermission("alerts.manage") ? <Button size="small" onClick={() => resolveAlert.mutate(row)}>{copy.resolve}</Button> : null}</Space> },
    ]} /></Card> : null}

    <Drawer width={600} open={ruleDrawer} title={editingRule ? copy.editRule : copy.newRule} onClose={() => setRuleDrawer(false)} extra={<Button type="primary" loading={saveRule.isPending} onClick={() => void ruleForm.validateFields().then((values) => saveRule.mutate(values))}>{copy.save}</Button>}>
      <Alert type="warning" showIcon message={copy.createdDisabled} className="drawer-alert" />
      <Form form={ruleForm} layout="vertical" requiredMark={false}>
        <Form.Item name="name" label={copy.name} rules={[{ required: true, max: 160 }]}><Input /></Form.Item>
        <Form.Item name="description" label={copy.descriptionField}><Input.TextArea rows={2} /></Form.Item>
        <Row gutter={12}><Col span={12}><Form.Item name="priority" label={copy.order} rules={[{ required: true }]}><InputNumber min={1} max={1000} style={{ width: "100%" }} /></Form.Item></Col>{editingRule ? <Col span={12}><Form.Item name="is_enabled" label={copy.enabled} valuePropName="checked"><Switch /></Form.Item></Col> : null}</Row>
        <Typography.Title level={5}>{copy.conditions}</Typography.Title>
        <Form.Item name="status_codes" label={copy.statuses}><Select mode="multiple" options={statusCodes.map((value) => ({ value, label: value }))} /></Form.Item>
        <Form.Item name="payment_statuses" label={copy.payments}><Select mode="tags" tokenSeparators={[","]} options={["draft", "created", "pending", "paid", "canceled", "error", "refunded"].map((value) => ({ value, label: value }))} /></Form.Item>
        <Form.Item name="min_age_minutes" label={copy.minAge} rules={[{ required: true }]}><InputNumber min={5} max={43200} style={{ width: "100%" }} /></Form.Item>
        <Space direction="vertical" className="automation-checks"><Form.Item name="missing_delivery" valuePropName="checked" noStyle><Checkbox>{copy.missingDelivery}</Checkbox></Form.Item><Form.Item name="missing_moysklad" valuePropName="checked" noStyle><Checkbox>{copy.missingMoysklad}</Checkbox></Form.Item><Form.Item name="only_active" valuePropName="checked" noStyle><Checkbox>{copy.onlyActive}</Checkbox></Form.Item></Space>
        <Typography.Title level={5} className="automation-section-title">{copy.action}</Typography.Title>
        <Form.Item name="action_kind" rules={[{ required: true }]}><Select options={[{ value: "create_task", label: copy.createTask }, { value: "queue_operation", label: copy.queueOperation }, { value: "push_customer", label: copy.pushCustomer }]} /></Form.Item>
        {actionKind === "create_task" ? <><Form.Item name="assignee_user_id" label={copy.assignee} rules={[{ required: true }]}><Select options={(assignees.data || []).map((row) => ({ value: row.user_id, label: row.name }))} /></Form.Item><Form.Item name="task_title" label={copy.taskTitle} rules={[{ required: true, max: 240 }]}><Input /></Form.Item><Form.Item name="task_description" label={copy.descriptionField}><Input.TextArea rows={3} /></Form.Item><Row gutter={12}><Col span={12}><Form.Item name="task_priority" label={copy.taskPriority}><Select options={["low", "normal", "high", "urgent"].map((value) => ({ value, label: value }))} /></Form.Item></Col><Col span={12}><Form.Item name="due_minutes" label={copy.dueMinutes}><InputNumber min={5} max={43200} style={{ width: "100%" }} /></Form.Item></Col></Row></> : null}
        {actionKind === "queue_operation" ? <Form.Item name="operation" label={copy.operation} rules={[{ required: true }]}><Select options={[{ value: "payment_check", label: "IntellectMoney · payment check" }, { value: "moysklad_sync", label: "МойСклад · sync" }, { value: "delivery_create", label: "Delivery · create" }]} /></Form.Item> : null}
        {actionKind === "push_customer" ? <><Form.Item name="push_title" label={copy.pushTitle} rules={[{ required: true, max: 180 }]}><Input /></Form.Item><Form.Item name="push_body" label={copy.pushBody} rules={[{ required: true, max: 500 }]}><Input.TextArea rows={4} /></Form.Item><Form.Item name="deep_link" label={copy.deepLink} rules={[{ pattern: /^\/(?!\/)/ }]}><Input placeholder="/orders" /></Form.Item></> : null}
      </Form>
    </Drawer>

    <Drawer width={720} open={Boolean(historyRule)} title={`${copy.history}: ${historyRule?.name || ""}`} onClose={() => setHistoryRule(null)}><Table<OrderAutomationExecution> rowKey="id" loading={executions.isLoading} dataSource={executions.data?.items} pagination={false} columns={[
      { title: copy.occurred, dataIndex: "executed_at", render: (value: string) => dateTime(value, locale) },
      { title: "Order", render: (_: unknown, row) => <Link to={`/sales/orders/${row.order_id}`}>{row.order_code}</Link> },
      { title: copy.action, dataIndex: "action_kind" },
      { title: "Status", dataIndex: "status", render: (value: string) => <Tag color={executionColors[value]}>{value}</Tag> },
      { title: "Error", dataIndex: "error", render: (value: string | null) => value || "—" },
    ]} /></Drawer>

    <Drawer width={720} open={Boolean(previewRule)} title={`${copy.preview}: ${previewRule?.name || ""}`} onClose={() => setPreviewRule(null)}>
      <Statistic title={copy.matches} value={preview.data?.matched || 0} className="drawer-statistic" />
      <Table<OrderAutomationPreview["sample"][number]> rowKey="order_id" loading={preview.isLoading} dataSource={preview.data?.sample} pagination={false} columns={[
        { title: "Order", render: (_: unknown, row) => <Link to={`/sales/orders/${row.order_id}`}>{row.order_code}</Link> },
        { title: copy.statuses, dataIndex: "status_code", render: (value: string) => <Tag>{value}</Tag> },
        { title: copy.payments, dataIndex: "payment_status" },
        { title: copy.customer, dataIndex: "customer_name" },
        { title: copy.occurred, dataIndex: "created_at", render: (value: string) => dateTime(value, locale) },
      ]} />
    </Drawer>

    <Drawer width={480} open={policyDrawer} title={editingPolicy ? (locale === "ru" ? editingPolicy.name_ru : editingPolicy.name_en) : "SLA"} onClose={() => setPolicyDrawer(false)} extra={<Button type="primary" loading={savePolicy.isPending} onClick={() => void policyForm.validateFields().then((values) => savePolicy.mutate(values))}>{copy.save}</Button>}><Form form={policyForm} layout="vertical"><Form.Item name="response_minutes" label={copy.response} rules={[{ required: true }]}><InputNumber min={5} max={10080} style={{ width: "100%" }} addonAfter={copy.minutes} /></Form.Item><Form.Item name="resolution_minutes" label={copy.resolution} rules={[{ required: true }]}><InputNumber min={15} max={43200} style={{ width: "100%" }} addonAfter={copy.minutes} /></Form.Item><Form.Item name="is_enabled" label={copy.enabled} valuePropName="checked"><Switch /></Form.Item></Form></Drawer>
  </div>
}
