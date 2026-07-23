import {
  ArrowUpOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CommentOutlined,
  CheckSquareOutlined,
  DollarOutlined,
  ShoppingCartOutlined,
  TeamOutlined,
  WarningOutlined,
  SettingOutlined,
} from "@ant-design/icons"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Button, Card, Checkbox, Col, Drawer, List, Progress, Row, Space, Statistic, Tag, Typography } from "antd"
import { useState } from "react"
import { apiRequest } from "../api/client"
import type { Dashboard, DashboardPreference } from "../api/types"
import { PageHeader } from "../components/PageHeader"
import { QueryState } from "../components/QueryState"
import { useLanguage } from "../i18n/LanguageProvider"
import { money } from "../utils/format"

export function DashboardPage() {
  const { locale } = useLanguage()
  const queryClient = useQueryClient()
  const [customizeOpen, setCustomizeOpen] = useState(false)
  const [draftWidgets, setDraftWidgets] = useState<string[]>([])
  const query = useQuery({ queryKey: ["dashboard"], queryFn: () => apiRequest<Dashboard>("/dashboard"), refetchInterval: 60_000 })
  const preferences = useQuery({ queryKey: ["dashboard-preferences"], queryFn: () => apiRequest<DashboardPreference>("/dashboard/preferences") })
  const data = query.data
  const copy = locale === "ru"
    ? { title: "Главная", description: "Состояние магазина за последние 30 дней", revenue: "Выручка", paid: "Оплаченные заказы", average: "Средний чек", customers: "Новые клиенты", attention: "Требует внимания", trend: "Динамика выручки", payment: "Ошибки оплаты", reviews: "Отзывы на модерации", stock: "Низкие остатки", baskets: "Брошенные корзины", integrations: "Ошибки интеграций", tasks: "Просроченные задачи", sla: "SLA команды", compliance: "Соблюдение SLA", breached: "Нарушенные задачи", customize: "Настроить", widgets: "Виджеты", save: "Сохранить" }
    : { title: "Dashboard", description: "Store performance for the last 30 days", revenue: "Revenue", paid: "Paid orders", average: "Average order", customers: "New customers", attention: "Needs attention", trend: "Revenue trend", payment: "Payment errors", reviews: "Reviews to moderate", stock: "Low stock", baskets: "Abandoned baskets", integrations: "Integration errors", tasks: "Overdue tasks", sla: "Team SLA", compliance: "SLA compliance", breached: "Breached tasks", customize: "Customize", widgets: "Widgets", save: "Save" }
  const widgets = preferences.data?.widgets || ["revenue", "paid_orders", "average_order", "new_customers", "revenue_trend", "attention", "sla"]
  const visible = (code: string) => widgets.includes(code)
  const widgetOptions = [
    ["revenue", copy.revenue], ["paid_orders", copy.paid], ["average_order", copy.average], ["new_customers", copy.customers], ["revenue_trend", copy.trend], ["attention", copy.attention], ["sla", copy.sla],
  ] as const
  const savePreferences = useMutation({
    mutationFn: () => apiRequest<DashboardPreference>("/dashboard/preferences", { method: "PUT", body: JSON.stringify({ widgets: draftWidgets, expected_updated_at: preferences.data?.updated_at || null }) }),
    onSuccess: () => { setCustomizeOpen(false); void queryClient.invalidateQueries({ queryKey: ["dashboard-preferences"] }) },
  })
  const maxTrend = Math.max(...(data?.revenue_trend.map((point) => Number(point.revenue)) || [1]), 1)
  const attention = data ? [
    { label: copy.payment, value: data.metrics.failed_payments, icon: <WarningOutlined />, color: "#dc2626" },
    { label: copy.reviews, value: data.metrics.pending_reviews, icon: <CommentOutlined />, color: "#d97706" },
    { label: copy.stock, value: data.metrics.low_stock_variants, icon: <ClockCircleOutlined />, color: "#2563eb" },
    { label: copy.baskets, value: data.metrics.abandoned_baskets, icon: <ShoppingCartOutlined />, color: "#7c3aed" },
    { label: copy.integrations, value: data.metrics.integration_errors, icon: <WarningOutlined />, color: "#dc2626" },
    { label: copy.tasks, value: data.metrics.overdue_tasks, icon: <CheckSquareOutlined />, color: "#b45309" },
  ] : []

  return (
    <div className="page-stack">
      <PageHeader title={copy.title} description={copy.description} actions={<Space><Tag color="green" icon={<CheckCircleOutlined />}>Live</Tag><Button icon={<SettingOutlined />} onClick={() => { setDraftWidgets(widgets); setCustomizeOpen(true) }}>{copy.customize}</Button></Space>} />
      <QueryState loading={query.isLoading} error={query.isError} onRetry={() => void query.refetch()} />
      {data ? (
        <>
          {widgets.some((code) => ["revenue", "paid_orders", "average_order", "new_customers"].includes(code)) ? <Row gutter={[16, 16]}>
            {visible("revenue") ? <Col xs={24} md={12} xl={6}><Card className="metric-card"><Statistic title={copy.revenue} value={money(data.metrics.revenue, "RUB", locale)} prefix={<DollarOutlined />} /><span className="metric-note positive"><ArrowUpOutlined /> 30 days</span></Card></Col> : null}
            {visible("paid_orders") ? <Col xs={24} md={12} xl={6}><Card className="metric-card"><Statistic title={copy.paid} value={data.metrics.paid_orders} prefix={<ShoppingCartOutlined />} /></Card></Col> : null}
            {visible("average_order") ? <Col xs={24} md={12} xl={6}><Card className="metric-card"><Statistic title={copy.average} value={money(data.metrics.average_order_value, "RUB", locale)} prefix={<DollarOutlined />} /></Card></Col> : null}
            {visible("new_customers") ? <Col xs={24} md={12} xl={6}><Card className="metric-card"><Statistic title={copy.customers} value={data.metrics.new_customers} prefix={<TeamOutlined />} /></Card></Col> : null}
          </Row> : null}
          <Row gutter={[16, 16]}>
            {visible("revenue_trend") ? <Col xs={24} xl={visible("attention") ? 16 : 24}>
              <Card title={copy.trend} className="chart-card">
                {data.revenue_trend.length ? (
                  <div className="bar-chart">
                    {data.revenue_trend.map((point) => (
                      <div className="bar-column" key={point.day} title={`${point.day}: ${money(point.revenue, "RUB", locale)}`}>
                        <div className="bar-value">{point.orders}</div>
                        <div className="bar" style={{ height: `${Math.max(8, (Number(point.revenue) / maxTrend) * 150)}px` }} />
                        <span>{point.day.slice(5)}</span>
                      </div>
                    ))}
                  </div>
                ) : <Typography.Text type="secondary">No sales in this period</Typography.Text>}
              </Card>
            </Col> : null}
            {visible("attention") ? <Col xs={24} xl={visible("revenue_trend") ? 8 : 24}>
              <Card title={copy.attention} className="attention-card">
                <List dataSource={attention} renderItem={(item) => (
                  <List.Item>
                    <Space><span className="attention-icon" style={{ color: item.color }}>{item.icon}</span><Typography.Text>{item.label}</Typography.Text></Space>
                    <Tag color={item.value ? "error" : "success"}>{item.value}</Tag>
                  </List.Item>
                )} />
                <Progress percent={attention.every((item) => item.value === 0) ? 100 : 72} showInfo={false} strokeColor="#0f766e" />
              </Card>
            </Col> : null}
          </Row>
          {visible("sla") ? <Card title={copy.sla} className="sla-dashboard-card"><Row gutter={[16, 16]}><Col xs={24} md={12}><Statistic title={copy.compliance} value={Number(data.metrics.sla_compliance_percent)} suffix="%" prefix={<CheckCircleOutlined />} /></Col><Col xs={24} md={12}><Statistic title={copy.breached} value={data.metrics.sla_breached_tasks} prefix={<CheckSquareOutlined />} valueStyle={{ color: data.metrics.sla_breached_tasks ? "#dc2626" : "#0f766e" }} /></Col></Row><Progress percent={Number(data.metrics.sla_compliance_percent)} showInfo={false} status={Number(data.metrics.sla_compliance_percent) < 80 ? "exception" : "normal"} /></Card> : null}
        </>
      ) : null}
      <Drawer title={copy.widgets} open={customizeOpen} width={400} onClose={() => setCustomizeOpen(false)} extra={<Button type="primary" disabled={!draftWidgets.length} loading={savePreferences.isPending} onClick={() => savePreferences.mutate()}>{copy.save}</Button>}><Checkbox.Group value={draftWidgets} onChange={(values) => setDraftWidgets(values as string[])} className="dashboard-widget-list">{widgetOptions.map(([value, label]) => <Checkbox key={value} value={value}>{label}</Checkbox>)}</Checkbox.Group></Drawer>
    </div>
  )
}
