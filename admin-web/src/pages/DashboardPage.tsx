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
import { Link } from "react-router-dom"
import { apiRequest } from "../api/client"
import type { Dashboard, DashboardPreference } from "../api/types"
import { useAuth } from "../auth/AuthProvider"
import { LinkedCard } from "../components/LinkedCard"
import { MetricLineChart } from "../components/MetricLineChart"
import { PageHeader } from "../components/PageHeader"
import { QueryState } from "../components/QueryState"
import { useLanguage } from "../i18n/LanguageProvider"
import { money } from "../utils/format"

export function DashboardPage() {
  const { locale } = useLanguage()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const [customizeOpen, setCustomizeOpen] = useState(false)
  const [draftWidgets, setDraftWidgets] = useState<string[]>([])
  const query = useQuery({ queryKey: ["dashboard"], queryFn: () => apiRequest<Dashboard>("/dashboard"), refetchInterval: 30_000 })
  const preferences = useQuery({ queryKey: ["dashboard-preferences"], queryFn: () => apiRequest<DashboardPreference>("/dashboard/preferences") })
  const data = query.data
  const copy = locale === "ru"
    ? { title: "Главная", description: "Состояние магазина за последние 30 дней", revenue: "Выручка", paid: "Оплаченные заказы", average: "Средний чек", customers: "Новые клиенты", online: "Онлайн в приложении", attention: "Требует внимания", trend: "Динамика выручки", trendExplanation: "Выручка — сумма оплаченных заказов за день. Заказы — количество оплаченных заказов за тот же день.", noSales: "За этот период продаж нет", payment: "Ошибки оплаты", reviews: "Отзывы на модерации", stock: "Низкие остатки", baskets: "Брошенные корзины", integrations: "Ошибки интеграций", tasks: "Просроченные задачи", sla: "SLA команды", compliance: "Соблюдение SLA", breached: "Нарушенные задачи", customize: "Настроить", widgets: "Виджеты", save: "Сохранить" }
    : { title: "Dashboard", description: "Store performance for the last 30 days", revenue: "Revenue", paid: "Paid orders", average: "Average order", customers: "New customers", online: "Online in app", attention: "Needs attention", trend: "Revenue trend", trendExplanation: "Revenue is the value of paid orders per day. Orders is the number of paid orders on the same day.", noSales: "No sales in this period", payment: "Payment errors", reviews: "Reviews to moderate", stock: "Low stock", baskets: "Abandoned baskets", integrations: "Integration errors", tasks: "Overdue tasks", sla: "Team SLA", compliance: "SLA compliance", breached: "Breached tasks", customize: "Customize", widgets: "Widgets", save: "Save" }
  const widgets = preferences.data?.widgets || ["revenue", "paid_orders", "average_order", "new_customers", "revenue_trend", "attention", "sla"]
  const visible = (code: string) => widgets.includes(code)
  const widgetOptions = [
    ["revenue", copy.revenue], ["paid_orders", copy.paid], ["average_order", copy.average], ["new_customers", copy.customers], ["revenue_trend", copy.trend], ["attention", copy.attention], ["sla", copy.sla],
  ] as const
  const savePreferences = useMutation({
    mutationFn: () => apiRequest<DashboardPreference>("/dashboard/preferences", { method: "PUT", body: JSON.stringify({ widgets: draftWidgets, expected_updated_at: preferences.data?.updated_at || null }) }),
    onSuccess: () => { setCustomizeOpen(false); void queryClient.invalidateQueries({ queryKey: ["dashboard-preferences"] }) },
  })
  const attention = data ? [
    { label: copy.payment, value: data.metrics.failed_payments, icon: <WarningOutlined />, color: "#dc2626", path: hasPermission("orders.read") ? "/sales/orders?payment_status=failed" : null },
    { label: copy.reviews, value: data.metrics.pending_reviews, icon: <CommentOutlined />, color: "#d97706", path: hasPermission("reviews.read") ? "/content/reviews?status=pending" : null },
    { label: copy.stock, value: data.metrics.low_stock_variants, icon: <ClockCircleOutlined />, color: "#2563eb", path: hasPermission("catalog.read") ? "/catalog/products?low_stock=true" : null },
    { label: copy.baskets, value: data.metrics.abandoned_baskets, icon: <ShoppingCartOutlined />, color: "#7c3aed", path: hasPermission("analytics.read") ? "/analytics?tab=customers&days=30" : null },
    { label: copy.integrations, value: data.metrics.integration_errors, icon: <WarningOutlined />, color: "#dc2626", path: hasPermission("integrations.read") ? "/integrations?status=error#history" : null },
    { label: copy.tasks, value: data.metrics.overdue_tasks, icon: <CheckSquareOutlined />, color: "#b45309", path: hasPermission("tasks.read") ? "/tasks?overdue=true" : null },
  ] : []
  const salesAnalyticsPath = hasPermission("analytics.read") ? "/analytics?tab=sales&days=30" : undefined
  const customerAnalyticsPath = hasPermission("analytics.read") ? "/analytics?tab=customers&days=30" : undefined
  const slaPath = hasPermission("sla.read") ? "/automation?tab=sla" : undefined

  return (
    <div className="page-stack">
      <PageHeader title={copy.title} description={copy.description} actions={<Space><Tag color="green" icon={<TeamOutlined />} title={locale === "ru" ? `Авторизованные пользователи с активностью за последние ${data?.metrics.online_window_minutes ?? 5} мин.` : `Signed-in users active in the last ${data?.metrics.online_window_minutes ?? 5} min.`}>{copy.online}: {data?.metrics.online_customers ?? "—"}</Tag><Button icon={<SettingOutlined />} onClick={() => { setDraftWidgets(widgets); setCustomizeOpen(true) }}>{copy.customize}</Button></Space>} />
      <QueryState loading={query.isLoading} error={query.isError} onRetry={() => void query.refetch()} />
      {data ? (
        <>
          {widgets.some((code) => ["revenue", "paid_orders", "average_order", "new_customers"].includes(code)) ? <Row gutter={[16, 16]}>
            {visible("revenue") ? <Col xs={24} md={12} xl={6}><LinkedCard to={salesAnalyticsPath} linkLabel={copy.revenue} className="metric-card"><Statistic title={copy.revenue} value={money(data.metrics.revenue, "RUB", locale)} prefix={<DollarOutlined />} /><span className="metric-note positive"><ArrowUpOutlined /> {locale === "ru" ? "30 дней" : "30 days"}</span></LinkedCard></Col> : null}
            {visible("paid_orders") ? <Col xs={24} md={12} xl={6}><LinkedCard to={salesAnalyticsPath} linkLabel={copy.paid} className="metric-card"><Statistic title={copy.paid} value={data.metrics.paid_orders} prefix={<ShoppingCartOutlined />} /></LinkedCard></Col> : null}
            {visible("average_order") ? <Col xs={24} md={12} xl={6}><LinkedCard to={salesAnalyticsPath} linkLabel={copy.average} className="metric-card"><Statistic title={copy.average} value={money(data.metrics.average_order_value, "RUB", locale)} prefix={<DollarOutlined />} /></LinkedCard></Col> : null}
            {visible("new_customers") ? <Col xs={24} md={12} xl={6}><LinkedCard to={customerAnalyticsPath} linkLabel={copy.customers} className="metric-card"><Statistic title={copy.customers} value={data.metrics.new_customers} prefix={<TeamOutlined />} /></LinkedCard></Col> : null}
          </Row> : null}
          <Row gutter={[16, 16]}>
            {visible("revenue_trend") ? <Col xs={24} xl={visible("attention") ? 16 : 24}>
              <Card title={salesAnalyticsPath ? <Link className="section-navigation-link" to={salesAnalyticsPath}>{copy.trend}</Link> : copy.trend} className="chart-card">
                <MetricLineChart
                  ariaLabel={copy.trend}
                  emptyText={copy.noSales}
                  description={copy.trendExplanation}
                  data={data.revenue_trend.map((point) => ({ key: point.day, label: point.day.slice(5), tooltipLabel: point.day, values: { revenue: Number(point.revenue), orders: point.orders } }))}
                  series={[
                    { key: "revenue", label: copy.revenue, color: "#0f766e", formatValue: (value) => money(value, "RUB", locale) },
                    { key: "orders", label: copy.paid, color: "#6366f1", axis: "right", formatValue: (value) => new Intl.NumberFormat(locale === "ru" ? "ru-RU" : "en-US").format(value) },
                  ]}
                  leftAxisFormatter={(value) => new Intl.NumberFormat(locale === "ru" ? "ru-RU" : "en-US", { notation: "compact", maximumFractionDigits: 1 }).format(value)}
                />
              </Card>
            </Col> : null}
            {visible("attention") ? <Col xs={24} xl={visible("revenue_trend") ? 8 : 24}>
              <Card title={copy.attention} className="attention-card">
                <List dataSource={attention} renderItem={(item) => (
                  <List.Item className={item.path ? "attention-item-linked" : undefined}>
                    {item.path ? <Link className="attention-link" to={item.path}>
                      <Space><span className="attention-icon" style={{ color: item.color }}>{item.icon}</span><Typography.Text>{item.label}</Typography.Text></Space>
                      <Tag color={item.value ? "error" : "success"}>{item.value}</Tag>
                    </Link> : <>
                      <Space><span className="attention-icon" style={{ color: item.color }}>{item.icon}</span><Typography.Text>{item.label}</Typography.Text></Space>
                      <Tag color={item.value ? "error" : "success"}>{item.value}</Tag>
                    </>}
                  </List.Item>
                )} />
                <Progress percent={attention.every((item) => item.value === 0) ? 100 : 72} showInfo={false} strokeColor="#0f766e" />
              </Card>
            </Col> : null}
          </Row>
          {visible("sla") ? <Card title={slaPath ? <Link className="section-navigation-link" to={slaPath}>{copy.sla}</Link> : copy.sla} className="sla-dashboard-card"><Row gutter={[16, 16]}><Col xs={24} md={12}>{slaPath ? <Link className="statistic-navigation-link" to={slaPath}><Statistic title={copy.compliance} value={Number(data.metrics.sla_compliance_percent)} suffix="%" prefix={<CheckCircleOutlined />} /></Link> : <Statistic title={copy.compliance} value={Number(data.metrics.sla_compliance_percent)} suffix="%" prefix={<CheckCircleOutlined />} />}</Col><Col xs={24} md={12}>{hasPermission("tasks.read") ? <Link className="statistic-navigation-link" to="/tasks?sla_breached=true"><Statistic title={copy.breached} value={data.metrics.sla_breached_tasks} prefix={<CheckSquareOutlined />} valueStyle={{ color: data.metrics.sla_breached_tasks ? "#dc2626" : "#0f766e" }} /></Link> : <Statistic title={copy.breached} value={data.metrics.sla_breached_tasks} prefix={<CheckSquareOutlined />} valueStyle={{ color: data.metrics.sla_breached_tasks ? "#dc2626" : "#0f766e" }} />}</Col></Row><Progress percent={Number(data.metrics.sla_compliance_percent)} showInfo={false} status={Number(data.metrics.sla_compliance_percent) < 80 ? "exception" : "normal"} /></Card> : null}
        </>
      ) : null}
      <Drawer title={copy.widgets} open={customizeOpen} width={400} onClose={() => setCustomizeOpen(false)} extra={<Button type="primary" disabled={!draftWidgets.length} loading={savePreferences.isPending} onClick={() => savePreferences.mutate()}>{copy.save}</Button>}><Checkbox.Group value={draftWidgets} onChange={(values) => setDraftWidgets(values as string[])} className="dashboard-widget-list">{widgetOptions.map(([value, label]) => <Checkbox key={value} value={value}>{label}</Checkbox>)}</Checkbox.Group></Drawer>
    </div>
  )
}
