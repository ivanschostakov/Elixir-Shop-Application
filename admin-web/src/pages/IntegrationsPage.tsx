import { CheckCircleOutlined, CloudSyncOutlined, CloseCircleOutlined, PauseCircleOutlined, ReloadOutlined } from "@ant-design/icons"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Button, Card, Col, Descriptions, Row, Space, Table, Tag, Typography, message } from "antd"
import { apiRequest } from "../api/client"
import type { IntegrationRun, IntegrationStatus, Page } from "../api/types"
import { useAuth } from "../auth/AuthProvider"
import { PageHeader } from "../components/PageHeader"
import { useLanguage } from "../i18n/LanguageProvider"
import { dateTime } from "../utils/format"

const stateMeta = {
  healthy: { color: "green", icon: <CheckCircleOutlined /> },
  warning: { color: "orange", icon: <CloudSyncOutlined /> },
  error: { color: "red", icon: <CloseCircleOutlined /> },
  disabled: { color: "default", icon: <PauseCircleOutlined /> },
} as const

export function IntegrationsPage() {
  const { locale } = useLanguage()
  const { hasPermission } = useAuth()
  const client = useQueryClient()
  const integrations = useQuery({ queryKey: ["integrations"], queryFn: () => apiRequest<IntegrationStatus[]>("/integrations"), refetchInterval: 30_000 })
  const runs = useQuery({ queryKey: ["integration-runs"], queryFn: () => apiRequest<Page<IntegrationRun>>("/integrations/runs?limit=50") })
  const retry = useMutation({
    mutationFn: () => apiRequest<IntegrationRun>("/integrations/moysklad/retry", { method: "POST", body: JSON.stringify({ operation: "catalog_sync", idempotency_key: crypto.randomUUID() }) }),
    onSuccess: () => { void client.invalidateQueries({ queryKey: ["integrations"] }); void client.invalidateQueries({ queryKey: ["integration-runs"] }); void message.success(locale === "ru" ? "Синхронизация запущена" : "Sync started") },
    onError: (error: Error) => void message.error(error.message),
  })
  const copy = locale === "ru" ? { title: "Интеграции", description: "Состояние внешних сервисов и история фоновых операций", configured: "Настроена", disabled: "Не настроена", last: "Последний запуск", retry: "Синхронизировать каталог", history: "История операций", provider: "Сервис", operation: "Операция", status: "Статус", started: "Запущено", finished: "Завершено", error: "Ошибка" } : { title: "Integrations", description: "External service health and background operation history", configured: "Configured", disabled: "Not configured", last: "Last run", retry: "Sync catalog", history: "Run history", provider: "Provider", operation: "Operation", status: "Status", started: "Started", finished: "Finished", error: "Error" }

  return <div className="page-stack">
    <PageHeader title={copy.title} description={copy.description} actions={<Button icon={<ReloadOutlined />} onClick={() => { void integrations.refetch(); void runs.refetch() }} />} />
    <Row gutter={[16, 16]}>{(integrations.data || []).map((item) => <Col xs={24} md={12} xl={8} key={item.provider}><Card className="integration-card"><div className="integration-card-header"><span className={`integration-icon ${item.status}`}>{stateMeta[item.status].icon}</span><div><Typography.Title level={4}>{item.label}</Typography.Title><Tag color={stateMeta[item.status].color}>{item.status}</Tag></div></div><Descriptions column={1} size="small"><Descriptions.Item label={item.configured ? copy.configured : copy.disabled}>{item.configured ? "Yes" : "No"}</Descriptions.Item><Descriptions.Item label={copy.last}>{dateTime(item.last_run_at, locale)}</Descriptions.Item></Descriptions>{item.provider === "moysklad" && hasPermission("integrations.retry") ? <Button block icon={<CloudSyncOutlined />} loading={retry.isPending} onClick={() => retry.mutate()}>{copy.retry}</Button> : null}</Card></Col>)}</Row>
    <Card title={copy.history}>
      <Table<IntegrationRun> rowKey="id" loading={runs.isLoading} dataSource={runs.data?.items} pagination={false} expandable={{ expandedRowRender: (row) => row.error ? <Typography.Text type="danger">{row.error}</Typography.Text> : <pre className="json-preview">{JSON.stringify(row.counters_json, null, 2)}</pre> }} columns={[
        { title: copy.provider, dataIndex: "provider" },
        { title: copy.operation, dataIndex: "operation" },
        { title: copy.status, dataIndex: "status", render: (value: string) => <Tag color={value === "success" ? "green" : value === "error" ? "red" : "processing"}>{value}</Tag> },
        { title: copy.started, dataIndex: "started_at", render: (value: string) => dateTime(value, locale) },
        { title: copy.finished, dataIndex: "finished_at", render: (value: string | null) => dateTime(value, locale) },
      ]} />
    </Card>
  </div>
}
