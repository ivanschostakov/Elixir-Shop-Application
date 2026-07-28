import { DownloadOutlined, LineChartOutlined } from "@ant-design/icons"
import { useQuery } from "@tanstack/react-query"
import { Button, Card, Col, Progress, Row, Segmented, Space, Statistic, Table, Tabs, Tag, Typography, message } from "antd"
import { useMemo, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { apiDownload, apiRequest } from "../api/client"
import type { AnalyticsSnapshot } from "../api/types"
import { useAuth } from "../auth/AuthProvider"
import { LinkedCard } from "../components/LinkedCard"
import { PageHeader } from "../components/PageHeader"
import { QueryState } from "../components/QueryState"
import { useLanguage } from "../i18n/LanguageProvider"
import { domainLabel } from "../i18n/domain"
import { dateTime, money } from "../utils/format"

type AnalyticsSection = "sales" | "customers" | "products" | "discounts" | "marketing"

function downloadBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = fileName
  link.click()
  URL.revokeObjectURL(url)
}

export function analyticsCsvPath(section: AnalyticsSection, days: number) {
  return `/analytics/${section}.csv?days=${days}`
}

export function AnalyticsPage() {
  const { locale } = useLanguage()
  const { hasPermission } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedDays = Number(searchParams.get("days") || 30)
  const days = [7, 30, 90, 365].includes(requestedDays) ? requestedDays : 30
  const requestedTab = searchParams.get("tab") as AnalyticsSection | null
  const tab: AnalyticsSection = requestedTab && ["sales", "customers", "products", "discounts", "marketing"].includes(requestedTab) ? requestedTab : "sales"
  const [openGranularity, setOpenGranularity] = useState<"daily" | "monthly">("daily")
  const query = useQuery({ queryKey: ["analytics", days], queryFn: () => apiRequest<AnalyticsSnapshot>(`/analytics?days=${days}`), refetchInterval: 60_000 })
  const data = query.data
  const copy = locale === "ru"
    ? { title: "Аналитика", description: "Продажи, клиенты, товары, скидки и маркетинг", period: "Период", export: "CSV", sales: "Продажи", customers: "Клиенты", products: "Товары", discounts: "Скидки", marketing: "Маркетинг", revenue: "Выручка", paidOrders: "Оплаченные заказы", averageOrder: "Средний чек", units: "Единиц", repeat: "Повторные", trend: "Динамика", status: "Статус", count: "Кол-во", newCustomers: "Новые", active: "Активные", inactive: "Неактивные", abandoned: "Брошенные корзины", ltv: "LTV", orders: "Заказы", stock: "Остаток", lowStock: "Низкие остатки", source: "Источник", applications: "Применений", totalDiscount: "Сумма скидок", campaigns: "Кампании", delivery: "Доставка", clicks: "Клики", failures: "Ошибки", generated: "Обновлено", appOpens: "Открытия приложения", uniqueCustomers: "Уникальные клиенты", averageOpens: "Открытий на клиента", daily: "По дням", monthly: "По месяцам", views: "Просмотры", viewers: "Смотрели", conversion: "Конверсия в покупку", buyers: "Покупатели", referralProfiles: "Реферальные профили" }
    : { title: "Analytics", description: "Sales, customers, products, discounts and marketing", period: "Period", export: "CSV", sales: "Sales", customers: "Customers", products: "Products", discounts: "Discounts", marketing: "Marketing", revenue: "Revenue", paidOrders: "Paid orders", averageOrder: "Average order", units: "Units", repeat: "Repeat", trend: "Trend", status: "Status", count: "Count", newCustomers: "New", active: "Active", inactive: "Inactive", abandoned: "Abandoned carts", ltv: "LTV", orders: "Orders", stock: "Stock", lowStock: "Low stock", source: "Source", applications: "Applications", totalDiscount: "Discount total", campaigns: "Campaigns", delivery: "Delivery", clicks: "Clicks", failures: "Failures", generated: "Updated", appOpens: "App opens", uniqueCustomers: "Unique customers", averageOpens: "Opens per customer", daily: "Daily", monthly: "Monthly", views: "Views", viewers: "Viewers", conversion: "Purchase conversion", buyers: "Buyers", referralProfiles: "Referral profiles" }
  const maxRevenue = useMemo(() => Math.max(...(data?.sales.trend.map((point) => Number(point.revenue)) || [1]), 1), [data])
  const openTrend = data?.customers.app_opens[openGranularity] || []
  const maxOpens = useMemo(() => Math.max(...openTrend.map((point) => point.opens), 1), [openTrend])
  const exportCsv = async (section: AnalyticsSection) => {
    try {
      const result = await apiDownload(analyticsCsvPath(section, days))
      downloadBlob(result.blob, result.fileName || `analytics-${section}-${days}d.csv`)
    } catch (error) {
      void message.error((error as Error).message)
    }
  }
  const exportAction = <Button icon={<DownloadOutlined />} onClick={() => void exportCsv(tab)}>{copy.export}</Button>
  const paymentOrdersPath = (status: string) => {
    if (!hasPermission("orders.read")) return undefined
    const filter = ["error", "canceled"].includes(status) ? "failed" : status
    if (!["failed", "pending", "paid", "refunded"].includes(filter)) return undefined
    return `/sales/orders?payment_status=${encodeURIComponent(filter)}`
  }
  const productPath = (productId: number) => `/catalog/products?product_id=${productId}`

  return <div className="page-stack">
    <PageHeader
      title={copy.title}
      description={copy.description}
      actions={<Space><Segmented value={days} onChange={(value) => setSearchParams((current) => { const next = new URLSearchParams(current); next.set("days", String(value)); return next })} options={[7, 30, 90, 365].map((value) => ({ label: `${value}${locale === "ru" ? "д" : "d"}`, value }))} />{exportAction}</Space>}
    />
    <QueryState loading={query.isLoading} error={query.isError} empty={!data} onRetry={() => void query.refetch()} />
    {data ? <>
        <Typography.Text type="secondary">{copy.generated}: {dateTime(data.generated_at, locale)}</Typography.Text>
        <Tabs activeKey={tab} onChange={(key) => setSearchParams((current) => { const next = new URLSearchParams(current); next.set("tab", key); return next })} items={[
          { key: "sales", label: copy.sales },
          { key: "customers", label: copy.customers },
          { key: "products", label: copy.products },
          { key: "discounts", label: copy.discounts },
          { key: "marketing", label: copy.marketing },
        ]} />

        {tab === "sales" ? <>
          <Row gutter={[16, 16]}>
            <Col xs={24} md={6}><Card><Statistic title={copy.revenue} value={money(data.sales.summary.revenue, "RUB", locale)} /></Card></Col>
            <Col xs={24} md={6}><LinkedCard to={paymentOrdersPath("paid")} linkLabel={copy.paidOrders}><Statistic title={copy.paidOrders} value={data.sales.summary.paid_orders} /></LinkedCard></Col>
            <Col xs={24} md={6}><Card><Statistic title={copy.averageOrder} value={money(data.sales.summary.average_order_value, "RUB", locale)} /></Card></Col>
            <Col xs={24} md={6}><Card><Statistic title={copy.repeat} value={`${data.sales.summary.repeat_rate}%`} /></Card></Col>
          </Row>
          <Card title={<Space><LineChartOutlined />{copy.trend}</Space>}>
            <div className="analytics-bars">{data.sales.trend.map((point) => <div key={point.date} className="analytics-bar-column" title={`${point.date}: ${money(point.revenue, "RUB", locale)}`}><div className="analytics-bar" style={{ height: `${Math.max(8, Number(point.revenue) / maxRevenue * 160)}px` }} /><small>{String(point.date).slice(5)}</small></div>)}</div>
          </Card>
          <Table rowKey="status" dataSource={data.sales.payment_statuses} pagination={false} columns={[{ title: copy.status, dataIndex: "status", render: (value: string) => paymentOrdersPath(value) ? <Link to={paymentOrdersPath(value)!}><Tag className="navigation-tag">{domainLabel(value, locale)}</Tag></Link> : <Tag>{domainLabel(value, locale)}</Tag> }, { title: copy.count, dataIndex: "count", align: "right", render: (value: number, row) => paymentOrdersPath(row.status) ? <Link className="table-value-link" to={paymentOrdersPath(row.status)!}>{value}</Link> : value }]} />
        </> : null}

        {tab === "customers" ? <>
          <Row gutter={[16, 16]}>
            <Col xs={24} md={6}><LinkedCard to={hasPermission("customers.read") ? "/customers" : undefined} linkLabel={copy.customers}><Statistic title={copy.customers} value={data.customers.summary.total_customers} /></LinkedCard></Col>
            <Col xs={24} md={6}><Card><Statistic title={copy.newCustomers} value={data.customers.summary.new_customers} /></Card></Col>
            <Col xs={24} md={6}><Card><Statistic title={copy.active} value={`${data.customers.summary.activation_rate}%`} /></Card></Col>
            <Col xs={24} md={6}><Card><Statistic title={copy.abandoned} value={data.customers.summary.abandoned_carts} /></Card></Col>
          </Row>
          <Row gutter={[16, 16]}>
            <Col xs={24} md={8}><Card><Statistic title={copy.appOpens} value={data.customers.app_opens.total} /></Card></Col>
            <Col xs={24} md={8}><Card><Statistic title={copy.uniqueCustomers} value={data.customers.app_opens.unique_customers} /></Card></Col>
            <Col xs={24} md={8}><Card><Statistic title={copy.averageOpens} value={data.customers.app_opens.average_per_customer} /></Card></Col>
          </Row>
          <Card
            title={<Space><LineChartOutlined />{copy.appOpens}</Space>}
            extra={<Segmented size="small" value={openGranularity} onChange={setOpenGranularity} options={[{ label: copy.daily, value: "daily" }, { label: copy.monthly, value: "monthly" }]} />}
          >
            {openTrend.length ? <div className="analytics-bars">{openTrend.map((point) => <div key={point.period} className="analytics-bar-column" title={`${String(point.period).slice(0, 10)}: ${point.opens} · ${copy.uniqueCustomers}: ${point.customers}`}><div className="analytics-bar" style={{ height: `${Math.max(8, point.opens / maxOpens * 160)}px` }} /><small>{openGranularity === "daily" ? String(point.period).slice(5, 10) : String(point.period).slice(0, 7)}</small></div>)}</div> : <Typography.Text type="secondary">{locale === "ru" ? "За выбранный период открытий нет" : "No app opens in this period"}</Typography.Text>}
          </Card>
          <Table rowKey="user_id" dataSource={data.customers.top_customers} pagination={{ pageSize: 10 }} columns={[{ title: copy.customers, render: (_: unknown, row) => <div className="table-primary">{hasPermission("customers.read") ? <Link to={`/customers/${row.user_id}`}><strong>{row.name}</strong></Link> : <strong>{row.name}</strong>}<small>{row.email || `#${row.user_id}`}</small></div> }, { title: copy.orders, dataIndex: "orders", align: "right" }, { title: copy.ltv, dataIndex: "ltv", render: (value: string) => money(value, "RUB", locale) }]} />
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={8}>
              <Card title={locale === "ru" ? "Платформы" : "Platforms"}>
                <Table rowKey="platform" size="small" dataSource={data.customers.devices.platforms} pagination={false} columns={[{ title: locale === "ru" ? "Платформа" : "Platform", dataIndex: "platform", render: (value: string) => <Tag>{domainLabel(value, locale)}</Tag> }, { title: copy.customers, dataIndex: "customers", align: "right" }]} />
              </Card>
            </Col>
            <Col xs={24} lg={8}>
              <Card title={locale === "ru" ? "Версии приложения" : "App versions"}>
                <Table rowKey={(row) => `${row.platform}-${row.app_version}`} size="small" dataSource={data.customers.devices.app_versions} pagination={{ pageSize: 8 }} columns={[{ title: locale === "ru" ? "Версия" : "Version", render: (_: unknown, row) => <Space><Tag>{domainLabel(row.platform, locale)}</Tag>{row.app_version}</Space> }, { title: copy.customers, dataIndex: "customers", align: "right" }]} />
              </Card>
            </Col>
            <Col xs={24} lg={8}>
              <Card title={locale === "ru" ? "Разрешение push" : "Push permission"}>
                <Table rowKey="permission" size="small" dataSource={data.customers.devices.push_permissions} pagination={false} columns={[{ title: copy.status, dataIndex: "permission", render: (value: string) => <Tag color={value === "granted" ? "green" : "default"}>{domainLabel(value, locale)}</Tag> }, { title: copy.customers, dataIndex: "customers", align: "right" }]} />
              </Card>
            </Col>
          </Row>
          <Card title={locale === "ru" ? "Поведенческие события" : "Behavior events"}>
            <Table rowKey="event_name" size="small" dataSource={data.customers.events} pagination={{ pageSize: 10 }} columns={[{ title: locale === "ru" ? "Событие" : "Event", dataIndex: "event_name", render: (value: string) => <Tag color="blue">{domainLabel(value, locale)}</Tag> }, { title: locale === "ru" ? "Событий" : "Events", dataIndex: "events", align: "right" }, { title: copy.customers, dataIndex: "customers", align: "right" }]} />
          </Card>
        </> : null}

        {tab === "products" ? <>
          <Row gutter={[16, 16]}>
            <Col xs={24} md={6}><LinkedCard to={hasPermission("catalog.read") ? "/catalog/products" : undefined} linkLabel={copy.products}><Statistic title={copy.products} value={data.products.summary.active_products} /></LinkedCard></Col>
            <Col xs={24} md={6}><Card><Statistic title={copy.active} value={`${data.products.summary.stock_coverage_rate}%`} /></Card></Col>
            <Col xs={24} md={6}><LinkedCard to={hasPermission("catalog.read") ? "/catalog/products?low_stock=true" : undefined} linkLabel={copy.lowStock}><Statistic title={copy.lowStock} value={data.products.summary.low_stock_products} /></LinkedCard></Col>
            <Col xs={24} md={6}><Card><Progress type="circle" size={68} percent={Number(data.products.summary.stock_coverage_rate)} /></Card></Col>
          </Row>
          <Table scroll={{ x: 1080 }} rowKey="product_id" dataSource={data.products.top_products} pagination={{ pageSize: 10 }} columns={[{ title: copy.products, fixed: "left", render: (_: unknown, row) => <div className="table-primary">{hasPermission("catalog.read") ? <Link to={productPath(row.product_id)}><strong>{row.name}</strong></Link> : <strong>{row.name}</strong>}<small>{row.sku}</small></div> }, { title: copy.units, dataIndex: "quantity", align: "right" }, { title: copy.orders, dataIndex: "orders", align: "right" }, { title: copy.buyers, dataIndex: "customers", align: "right" }, { title: copy.views, dataIndex: "views", align: "right" }, { title: copy.viewers, dataIndex: "viewers", align: "right" }, { title: copy.conversion, dataIndex: "conversion_rate", align: "right", render: (value: string) => `${value}%` }, { title: copy.stock, dataIndex: "stock", align: "right" }, { title: copy.revenue, dataIndex: "revenue", render: (value: string) => money(value, "RUB", locale) }]} />
          <Table rowKey="product_id" dataSource={data.products.low_stock} pagination={{ pageSize: 10 }} columns={[{ title: copy.lowStock, render: (_: unknown, row) => <div className="table-primary">{hasPermission("catalog.read") ? <Link to={productPath(row.product_id)}><strong>{row.name}</strong></Link> : <strong>{row.name}</strong>}<small>{row.sku}</small></div> }, { title: copy.stock, dataIndex: "stock", align: "right" }]} />
        </> : null}

        {tab === "discounts" ? <>
          <Row gutter={[16, 16]}>
            <Col xs={24} md={6}><Card><Statistic title={copy.totalDiscount} value={money(data.discounts.summary.total_discount, "RUB", locale)} /></Card></Col>
            <Col xs={24} md={6}><Card><Statistic title={copy.applications} value={data.discounts.summary.applications} /></Card></Col>
            <Col xs={24} md={6}><LinkedCard to={hasPermission("referrals.read") ? "/marketing?tab=referrals" : undefined} linkLabel={copy.referralProfiles}><Statistic title={copy.referralProfiles} value={data.discounts.summary.referral_profiles} /></LinkedCard></Col>
            <Col xs={24} md={6}><Card><Statistic title={copy.active} value={`${data.discounts.summary.active_referral_rate}%`} /></Card></Col>
          </Row>
          <Table rowKey="source" dataSource={data.discounts.sources} pagination={false} columns={[{ title: copy.source, dataIndex: "source", render: (value: string) => domainLabel(value, locale) }, { title: copy.applications, dataIndex: "applications", align: "right" }, { title: copy.totalDiscount, dataIndex: "discount_amount", render: (value: string) => money(value, "RUB", locale) }]} />
        </> : null}

        {tab === "marketing" ? <>
          <Row gutter={[16, 16]}>
            <Col xs={24} md={6}><LinkedCard to={hasPermission("campaigns.read") ? "/marketing?tab=campaigns" : undefined} linkLabel={copy.campaigns}><Statistic title={copy.campaigns} value={data.marketing.summary.campaigns} /></LinkedCard></Col>
            <Col xs={24} md={6}><Card><Statistic title={copy.delivery} value={`${data.marketing.summary.delivery_rate}%`} /></Card></Col>
            <Col xs={24} md={6}><Card><Statistic title={copy.clicks} value={`${data.marketing.summary.click_rate}%`} /></Card></Col>
            <Col xs={24} md={6}><Card><Statistic title={copy.failures} value={`${data.marketing.summary.failure_rate}%`} /></Card></Col>
          </Row>
          <Table rowKey="campaign_id" dataSource={data.marketing.campaigns} pagination={{ pageSize: 10 }} columns={[{ title: copy.campaigns, render: (_: unknown, row) => <div className="table-primary">{hasPermission("campaigns.read") ? <Link to={`/marketing?tab=campaigns&campaign_id=${row.campaign_id}`}><strong>{row.name}</strong></Link> : <strong>{row.name}</strong>}<small>{row.goal || domainLabel(row.status, locale)}</small></div> }, { title: copy.delivery, render: (_: unknown, row) => `${row.delivery_rate}%` }, { title: copy.clicks, render: (_: unknown, row) => `${row.click_rate}%` }, { title: copy.failures, dataIndex: "failed", align: "right" }, { title: copy.generated, dataIndex: "created_at", render: (value: string) => dateTime(value, locale) }]} />
        </> : null}
    </> : null}
  </div>
}
