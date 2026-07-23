import { CheckCircleOutlined, CloudSyncOutlined, CloseCircleOutlined, PauseCircleOutlined, ReloadOutlined } from "@ant-design/icons"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Button, Card, Col, Descriptions, Row, Space, Statistic, Table, Tag, Typography, message } from "antd"
import { apiRequest } from "../api/client"
import type { IntegrationQueueHealth, IntegrationRun, IntegrationStatus, Page } from "../api/types"
import { useAuth } from "../auth/AuthProvider"
import { PageHeader } from "../components/PageHeader"
import { QueryState } from "../components/QueryState"
import { useLanguage } from "../i18n/LanguageProvider"
import { dateTime } from "../utils/format"

const stateMeta = {
  healthy: { color: "green", icon: <CheckCircleOutlined /> },
  warning: { color: "orange", icon: <CloudSyncOutlined /> },
  error: { color: "red", icon: <CloseCircleOutlined /> },
  disabled: { color: "default", icon: <PauseCircleOutlined /> },
} as const

const runColor: Record<string, string> = {
  queued: "default",
  running: "processing",
  retrying: "warning",
  success: "success",
  error: "error",
}

export function IntegrationsPage() {
  const { locale } = useLanguage()
  const { hasPermission } = useAuth()
  const client = useQueryClient()
  const integrations = useQuery({ queryKey: ["integrations"], queryFn: () => apiRequest<IntegrationStatus[]>("/integrations"), refetchInterval: 30_000 })
  const runs = useQuery({ queryKey: ["integration-runs"], queryFn: () => apiRequest<Page<IntegrationRun>>("/integrations/runs?limit=50"), refetchInterval: 10_000 })
  const health = useQuery({ queryKey: ["integration-queue-health"], queryFn: () => apiRequest<IntegrationQueueHealth>("/integrations/queue-health"), refetchInterval: 15_000 })
  const refresh = () => {
    void integrations.refetch()
    void runs.refetch()
    void health.refetch()
  }
  const catalogSync = useMutation({
    mutationFn: () => apiRequest<IntegrationRun>("/integrations/moysklad/retry", { method: "POST", body: JSON.stringify({ operation: "catalog_sync", idempotency_key: crypto.randomUUID() }) }),
    onSuccess: () => { refresh(); void message.success(locale === "ru" ? "Синхронизация запущена" : "Sync started") },
    onError: (error: Error) => void message.error(error.message),
  })
  const retryRun = useMutation({
    mutationFn: (runId: number) => apiRequest<IntegrationRun>(`/integrations/runs/${runId}/retry`, { method: "POST", body: JSON.stringify({ idempotency_key: crypto.randomUUID() }) }),
    onSuccess: () => { void client.invalidateQueries({ queryKey: ["integration-runs"] }); void client.invalidateQueries({ queryKey: ["integration-queue-health"] }); void message.success(locale === "ru" ? "Повтор запущен" : "Retry started") },
    onError: (error: Error) => void message.error(error.message),
  })
  const copy = locale === "ru"
    ? { title: "Интеграции", description: "Состояние сервисов и восстановление фоновых операций", configured: "Настроена", disabled: "Не настроена", last: "Последний запуск", sync: "Синхронизировать каталог", history: "История операций", provider: "Сервис", operation: "Операция", target: "Объект", status: "Статус", attempts: "Попытки", started: "Запущено", finished: "Завершено", actions: "", retry: "Повторить", queue: "Очередь", active: "В работе", scheduled: "Ожидают повтора", failed: "Ошибки за 24 часа", stale: "Зависшие", available: "Worker доступен", unavailable: "Worker недоступен" }
    : { title: "Integrations", description: "Service health and background operation recovery", configured: "Configured", disabled: "Not configured", last: "Last run", sync: "Sync catalog", history: "Operation history", provider: "Provider", operation: "Operation", target: "Target", status: "Status", attempts: "Attempts", started: "Started", finished: "Finished", actions: "", retry: "Retry", queue: "Queued", active: "Running", scheduled: "Retrying", failed: "Errors in 24 hours", stale: "Stale", available: "Worker available", unavailable: "Worker unavailable" }

  return <div className="page-stack">
    <PageHeader title={copy.title} description={copy.description} actions={<Button icon={<ReloadOutlined />} onClick={refresh} />} />
    <QueryState loading={health.isLoading} error={health.isError} onRetry={() => void health.refetch()} />
    {health.data ? <Card size="small" className="queue-health-card">
      <div className="queue-health-grid">
        <Statistic title={copy.queue} value={health.data.queued + health.data.queue_depth} />
        <Statistic title={copy.active} value={health.data.running + health.data.processing_depth} />
        <Statistic title={copy.scheduled} value={health.data.retrying + health.data.scheduled_depth} />
        <Statistic title={copy.failed} value={health.data.failed_24h} valueStyle={health.data.failed_24h ? { color: "#b42318" } : undefined} />
        <Statistic title={copy.stale} value={health.data.stale_running} valueStyle={health.data.stale_running ? { color: "#b42318" } : undefined} />
        <Tag color={health.data.queue_available ? "success" : "error"}>{health.data.queue_available ? copy.available : copy.unavailable}</Tag>
      </div>
    </Card> : null}
    <Row gutter={[16, 16]}>{(integrations.data || []).map((item) => <Col xs={24} md={12} xl={8} key={item.provider}><Card className="integration-card"><div className="integration-card-header"><span className={`integration-icon ${item.status}`}>{stateMeta[item.status].icon}</span><div><Typography.Title level={4}>{item.label}</Typography.Title><Tag color={stateMeta[item.status].color}>{item.status}</Tag></div></div><Descriptions column={1} size="small"><Descriptions.Item label={item.configured ? copy.configured : copy.disabled}>{item.configured ? "Yes" : "No"}</Descriptions.Item><Descriptions.Item label={copy.last}>{dateTime(item.last_run_at, locale)}</Descriptions.Item></Descriptions>{item.provider === "moysklad" && hasPermission("integrations.retry") ? <Button block icon={<CloudSyncOutlined />} loading={catalogSync.isPending} onClick={() => catalogSync.mutate()}>{copy.sync}</Button> : null}</Card></Col>)}</Row>
    <Card title={copy.history}>
      <Table<IntegrationRun> rowKey="id" loading={runs.isLoading} dataSource={runs.data?.items} pagination={false} scroll={{ x: 980 }} expandable={{ expandedRowRender: (row) => row.error ? <Typography.Text type="danger">{row.error}</Typography.Text> : <pre className="json-preview">{JSON.stringify(row.counters_json, null, 2)}</pre> }} columns={[
        { title: copy.provider, dataIndex: "provider" },
        { title: copy.operation, dataIndex: "operation" },
        { title: copy.target, key: "target", render: (_, row) => row.target_type ? `${row.target_type} #${row.target_id}` : "—" },
        { title: copy.status, dataIndex: "status", render: (value: string) => <Tag color={runColor[value] || "default"}>{value}</Tag> },
        { title: copy.attempts, key: "attempts", render: (_, row) => `${row.attempts}/${row.max_attempts}` },
        { title: copy.started, dataIndex: "started_at", render: (value: string) => dateTime(value, locale) },
        { title: copy.finished, dataIndex: "finished_at", render: (value: string | null, row) => dateTime(value || row.next_attempt_at, locale) },
        { title: copy.actions, key: "actions", width: 110, render: (_, row) => row.status === "error" && hasPermission("integrations.retry") ? <Button size="small" loading={retryRun.isPending && retryRun.variables === row.id} onClick={() => retryRun.mutate(row.id)}>{copy.retry}</Button> : null },
      ]} />
    </Card>
  </div>
}
