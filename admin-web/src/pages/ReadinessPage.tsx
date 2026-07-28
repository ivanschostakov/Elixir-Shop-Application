import { CheckCircleOutlined, CloseCircleOutlined, ExclamationCircleOutlined, QuestionCircleOutlined, ReloadOutlined } from "@ant-design/icons"
import { useQuery } from "@tanstack/react-query"
import { Button, Card, Col, Row, Space, Statistic, Table, Tag, Typography } from "antd"
import { Link } from "react-router-dom"
import { apiRequest } from "../api/client"
import type { ProductionReadiness, ReadinessCheck, WorkerHeartbeat } from "../api/types"
import { useAuth } from "../auth/AuthProvider"
import { PageHeader } from "../components/PageHeader"
import { QueryState } from "../components/QueryState"
import { useLanguage } from "../i18n/LanguageProvider"
import { domainLabel } from "../i18n/domain"
import { dateTime } from "../utils/format"

const statusMeta = {
  ok: { color: "green", icon: <CheckCircleOutlined /> },
  warning: { color: "orange", icon: <ExclamationCircleOutlined /> },
  error: { color: "red", icon: <CloseCircleOutlined /> },
  unknown: { color: "default", icon: <QuestionCircleOutlined /> },
} as const

export function ReadinessPage() {
  const { locale } = useLanguage()
  const { hasPermission } = useAuth()
  const readiness = useQuery({
    queryKey: ["production-readiness"],
    queryFn: () => apiRequest<ProductionReadiness>("/integrations/production-readiness"),
    refetchInterval: 20_000,
  })
  const copy = locale === "ru"
    ? { title: "Готовность", description: "Продакшен-чеклист админки", status: "Статус", check: "Проверка", message: "Состояние", details: "Детали", workers: "Фоновые обработчики", lastSeen: "Пульс", staleAfter: "Считать устаревшим", generated: "Обновлено", host: "Сервер", healthy: "Работает", warning: "Внимание", error: "Ошибка", unknown: "Неизвестно", checklist: "Чеклист" }
    : { title: "Readiness", description: "Admin production checklist", status: "Status", check: "Check", message: "State", details: "Details", workers: "Workers", lastSeen: "Heartbeat", staleAfter: "Stale after", generated: "Updated", host: "Host", healthy: "OK", warning: "Warning", error: "Error", unknown: "Unknown", checklist: "Checklist" }
  const label = (check: ReadinessCheck) => locale === "ru" ? check.label_ru : check.label_en
  const message = (check: ReadinessCheck) => locale === "ru" ? check.message_ru : check.message_en
  const statusText = (status: keyof typeof statusMeta) => {
    if (status === "ok") return copy.healthy
    if (status === "warning") return copy.warning
    if (status === "error") return copy.error
    return copy.unknown
  }
  const checkPath = (key: string) => {
    if (["queues", "workers", "integrations"].includes(key) && hasPermission("integrations.read")) return "/integrations"
    if (key === "active_alerts" && hasPermission("alerts.read")) return "/automation?tab=alerts"
    if (["rbac_mfa", "security_config"].includes(key) && hasPermission("staff.manage")) return "/settings/staff"
    return undefined
  }

  return <div className="page-stack">
    <PageHeader title={copy.title} description={copy.description} actions={<Button icon={<ReloadOutlined />} onClick={() => void readiness.refetch()} />} />
    <QueryState loading={readiness.isLoading} error={readiness.isError} onRetry={() => void readiness.refetch()} />
    {readiness.data ? <>
      <Row gutter={[16, 16]}>
        <Col xs={24} md={6}><Card><Statistic title={copy.status} value={statusText(readiness.data.overall_status)} prefix={statusMeta[readiness.data.overall_status].icon} valueStyle={{ color: readiness.data.overall_status === "error" ? "#b42318" : readiness.data.overall_status === "warning" ? "#b45309" : "#0f766e" }} /></Card></Col>
        <Col xs={24} md={6}><Card><Statistic title={copy.checklist} value={`${readiness.data.checklist_summary.ok || 0}/${readiness.data.checks.length}`} suffix={<Space size={4}><Tag color="orange">{readiness.data.checklist_summary.warning || 0}</Tag><Tag color="red">{readiness.data.checklist_summary.error || 0}</Tag><Tag>{readiness.data.checklist_summary.unknown || 0}</Tag></Space>} /></Card></Col>
        <Col xs={24} md={6}><Card><Statistic title={copy.generated} value={dateTime(readiness.data.generated_at, locale)} /></Card></Col>
        <Col xs={24} md={6}><Card><Statistic title={copy.host} value={readiness.data.public_host || "—"} /></Card></Col>
      </Row>
      <Card>
        <Table<ReadinessCheck>
          rowKey="key"
          dataSource={readiness.data.checks}
          pagination={false}
          scroll={{ x: 860 }}
          columns={[
            { title: copy.status, width: 130, render: (_: unknown, row) => <Tag icon={statusMeta[row.status].icon} color={statusMeta[row.status].color}>{statusText(row.status)}</Tag> },
            { title: copy.check, render: (_: unknown, row) => checkPath(row.key) ? <Link to={checkPath(row.key)!}><Typography.Text strong>{label(row)}</Typography.Text></Link> : <Typography.Text strong>{label(row)}</Typography.Text> },
            { title: copy.message, render: (_: unknown, row) => <Typography.Text type={row.status === "error" ? "danger" : undefined}>{message(row)}</Typography.Text> },
            { title: copy.details, render: (_: unknown, row) => Object.keys(row.details || {}).length ? <Typography.Text code>{JSON.stringify(row.details)}</Typography.Text> : "—" },
          ]}
        />
      </Card>
      <Card title={copy.workers}>
        <Table<WorkerHeartbeat>
          rowKey="name"
          dataSource={readiness.data.workers}
          pagination={false}
          columns={[
            { title: copy.check, dataIndex: "name", render: (value: string) => hasPermission("integrations.read") ? <Link to="/integrations">{domainLabel(value, locale)}</Link> : domainLabel(value, locale) },
            { title: copy.status, render: (_: unknown, row) => <Tag color={statusMeta[row.status].color}>{statusText(row.status)}</Tag> },
            { title: copy.lastSeen, dataIndex: "last_seen_at", render: (value: string | null) => dateTime(value, locale) },
            { title: copy.staleAfter, dataIndex: "stale_after_seconds", render: (value: number) => `${value} ${locale === "ru" ? "с" : "s"}` },
          ]}
        />
      </Card>
    </> : null}
  </div>
}
