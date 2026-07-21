import {
  ArrowUpOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CommentOutlined,
  DollarOutlined,
  ShoppingCartOutlined,
  TeamOutlined,
  WarningOutlined,
} from "@ant-design/icons"
import { useQuery } from "@tanstack/react-query"
import { Card, Col, List, Progress, Row, Space, Statistic, Tag, Typography } from "antd"
import { apiRequest } from "../api/client"
import type { Dashboard } from "../api/types"
import { PageHeader } from "../components/PageHeader"
import { QueryState } from "../components/QueryState"
import { useLanguage } from "../i18n/LanguageProvider"
import { money } from "../utils/format"

export function DashboardPage() {
  const { locale } = useLanguage()
  const query = useQuery({ queryKey: ["dashboard"], queryFn: () => apiRequest<Dashboard>("/dashboard"), refetchInterval: 60_000 })
  const data = query.data
  const copy = locale === "ru"
    ? { title: "Главная", description: "Состояние магазина за последние 30 дней", revenue: "Выручка", paid: "Оплаченные заказы", average: "Средний чек", customers: "Новые клиенты", attention: "Требует внимания", trend: "Динамика выручки", payment: "Ошибки оплаты", reviews: "Отзывы на модерации", stock: "Низкие остатки", baskets: "Брошенные корзины", integrations: "Ошибки интеграций" }
    : { title: "Dashboard", description: "Store performance for the last 30 days", revenue: "Revenue", paid: "Paid orders", average: "Average order", customers: "New customers", attention: "Needs attention", trend: "Revenue trend", payment: "Payment errors", reviews: "Reviews to moderate", stock: "Low stock", baskets: "Abandoned baskets", integrations: "Integration errors" }
  const maxTrend = Math.max(...(data?.revenue_trend.map((point) => Number(point.revenue)) || [1]), 1)
  const attention = data ? [
    { label: copy.payment, value: data.metrics.failed_payments, icon: <WarningOutlined />, color: "#dc2626" },
    { label: copy.reviews, value: data.metrics.pending_reviews, icon: <CommentOutlined />, color: "#d97706" },
    { label: copy.stock, value: data.metrics.low_stock_variants, icon: <ClockCircleOutlined />, color: "#2563eb" },
    { label: copy.baskets, value: data.metrics.abandoned_baskets, icon: <ShoppingCartOutlined />, color: "#7c3aed" },
    { label: copy.integrations, value: data.metrics.integration_errors, icon: <WarningOutlined />, color: "#dc2626" },
  ] : []

  return (
    <div className="page-stack">
      <PageHeader title={copy.title} description={copy.description} actions={<Tag color="green" icon={<CheckCircleOutlined />}>Live</Tag>} />
      <QueryState loading={query.isLoading} error={query.isError} onRetry={() => void query.refetch()} />
      {data ? (
        <>
          <Row gutter={[16, 16]}>
            <Col xs={24} md={12} xl={6}><Card className="metric-card"><Statistic title={copy.revenue} value={money(data.metrics.revenue, "RUB", locale)} prefix={<DollarOutlined />} /><span className="metric-note positive"><ArrowUpOutlined /> 30 days</span></Card></Col>
            <Col xs={24} md={12} xl={6}><Card className="metric-card"><Statistic title={copy.paid} value={data.metrics.paid_orders} prefix={<ShoppingCartOutlined />} /></Card></Col>
            <Col xs={24} md={12} xl={6}><Card className="metric-card"><Statistic title={copy.average} value={money(data.metrics.average_order_value, "RUB", locale)} prefix={<DollarOutlined />} /></Card></Col>
            <Col xs={24} md={12} xl={6}><Card className="metric-card"><Statistic title={copy.customers} value={data.metrics.new_customers} prefix={<TeamOutlined />} /></Card></Col>
          </Row>
          <Row gutter={[16, 16]}>
            <Col xs={24} xl={16}>
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
            </Col>
            <Col xs={24} xl={8}>
              <Card title={copy.attention} className="attention-card">
                <List dataSource={attention} renderItem={(item) => (
                  <List.Item>
                    <Space><span className="attention-icon" style={{ color: item.color }}>{item.icon}</span><Typography.Text>{item.label}</Typography.Text></Space>
                    <Tag color={item.value ? "error" : "success"}>{item.value}</Tag>
                  </List.Item>
                )} />
                <Progress percent={attention.every((item) => item.value === 0) ? 100 : 72} showInfo={false} strokeColor="#0f766e" />
              </Card>
            </Col>
          </Row>
        </>
      ) : null}
    </div>
  )
}
