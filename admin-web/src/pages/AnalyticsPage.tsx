import { DownloadOutlined, LineChartOutlined } from "@ant-design/icons"
import { useQuery } from "@tanstack/react-query"
import { Button, Card, Col, DatePicker, Progress, Row, Segmented, Space, Statistic, Table, Tabs, Tag, Typography, message } from "antd"
import dayjs from "dayjs"
import { useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { apiDownload, apiRequest } from "../api/client"
import type { AnalyticsSnapshot } from "../api/types"
import { useAuth } from "../auth/AuthProvider"
import { LinkedCard } from "../components/LinkedCard"
import { MetricLineChart } from "../components/MetricLineChart"
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

type DateRange = [string, string]
function analyticsQuery(days: number, range?: DateRange) {
  return new URLSearchParams(range ? { date_from: range[0], date_to: range[1] } : { days: String(days) }).toString()
}
export function analyticsCsvPath(section: AnalyticsSection, days: number, range?: DateRange) {
  return `/analytics/${section}.csv?${analyticsQuery(days, range)}`
}

export function AnalyticsPage() {
  const { locale } = useLanguage()
  const { hasPermission } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedDays = Number(searchParams.get("days") || 30)
  const days = [7, 30, 90, 365].includes(requestedDays) ? requestedDays : 30
  const from = searchParams.get("date_from"), to = searchParams.get("date_to")
  const range: DateRange | undefined = from && to ? [from, to] : undefined
  const periodQuery = analyticsQuery(days, range)
  const selectPeriod = (preset: number, dates?: DateRange) => setSearchParams(current => {
    const next = new URLSearchParams(current)
    next.delete("days"); next.delete("date_from"); next.delete("date_to")
    new URLSearchParams(analyticsQuery(preset, dates)).forEach((v, k) => next.set(k, v))
    return next
  })
  const requestedTab = searchParams.get("tab") as AnalyticsSection | null
  const tab: AnalyticsSection = requestedTab && ["sales", "customers", "products", "discounts", "marketing"].includes(requestedTab) ? requestedTab : "sales"
  const [openGranularity, setOpenGranularity] = useState<"daily" | "monthly">("daily")
  const query = useQuery({ queryKey: ["analytics", periodQuery], queryFn: () => apiRequest<AnalyticsSnapshot>(`/analytics?${periodQuery}`), refetchInterval: 60_000 })
  const data = query.data
  const copy = locale === "ru"
    ? { title: "Аналитика", description: "Продажи, клиенты, товары, скидки и маркетинг", period: "Период", export: "CSV", sales: "Продажи", customers: "Клиенты", products: "Товары", discounts: "Скидки", marketing: "Маркетинг", revenue: "Выручка", paidOrders: "Оплаченные заказы", averageOrder: "Средний чек", units: "Единиц", repeat: "Повторные", trend: "Динамика", salesTrendExplanation: "Выручка — сумма оплаченных заказов за период. Оплаченные заказы — их количество; наведите на дату для точных значений.", status: "Статус", count: "Кол-во", newCustomers: "Новые", active: "Активные", inactive: "Неактивные", abandoned: "Брошенные корзины", ltv: "LTV", orders: "Заказы", stock: "Остаток", lowStock: "Низкие остатки", source: "Источник", applications: "Применений", totalDiscount: "Сумма скидок", campaigns: "Кампании", delivery: "Доставка", clicks: "Клики", failures: "Ошибки", generated: "Обновлено", appOpens: "Открытия приложения", uniqueCustomers: "Уникальные клиенты", averageOpens: "Открытий на клиента", opensExplanation: "Открытия — все зафиксированные запуски приложения. Уникальные клиенты — число разных авторизованных пользователей, открывавших приложение в периоде.", noOpens: "За выбранный период открытий нет", daily: "По дням", monthly: "По месяцам", views: "Просмотры", viewers: "Смотрели", conversion: "Конверсия в покупку", buyers: "Покупатели", referralProfiles: "Реферальные профили" }
    : { title: "Analytics", description: "Sales, customers, products, discounts and marketing", period: "Period", export: "CSV", sales: "Sales", customers: "Customers", products: "Products", discounts: "Discounts", marketing: "Marketing", revenue: "Revenue", paidOrders: "Paid orders", averageOrder: "Average order", units: "Units", repeat: "Repeat", trend: "Trend", salesTrendExplanation: "Revenue is the value of paid orders in the period. Paid orders is their count; hover a date for exact values.", status: "Status", count: "Count", newCustomers: "New", active: "Active", inactive: "Inactive", abandoned: "Abandoned carts", ltv: "LTV", orders: "Orders", stock: "Stock", lowStock: "Low stock", source: "Source", applications: "Applications", totalDiscount: "Discount total", campaigns: "Campaigns", delivery: "Delivery", clicks: "Clicks", failures: "Failures", generated: "Updated", appOpens: "App opens", uniqueCustomers: "Unique customers", averageOpens: "Opens per customer", opensExplanation: "Opens is every recorded app launch. Unique customers is the number of distinct signed-in users who opened the app in the period.", noOpens: "No app opens in this period", daily: "Daily", monthly: "Monthly", views: "Views", viewers: "Viewers", conversion: "Purchase conversion", buyers: "Buyers", referralProfiles: "Referral profiles" }
  const authTitle = locale === "ru" ? "Регистрации и входы по дням" : "Daily registrations and sign-ins"
  const registrationLabel = locale === "ru" ? "Регистрации" : "Registrations"
  const signInLabel = locale === "ru" ? "Входы" : "Sign-ins"
  const dailyAuth = data?.customers.auth_daily ?? []
  const openTrend = data?.customers.app_opens[openGranularity] || []
  const exportCsv = async (section: AnalyticsSection) => {
    try {
      const result = await apiDownload(analyticsCsvPath(section, days, range))
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
      actions={<Space wrap>
        <Segmented value={range ? "range" : days} onChange={value => selectPeriod(Number(value))}
          options={[7, 30, 90, 365].map(value => ({ label: `${value}${locale === "ru" ? "д" : "d"}`, value }))} />
        <DatePicker.RangePicker format="DD.MM.YYYY" placeholder={locale === "ru" ? ["С даты", "По дату"] : ["From date", "To date"]}
          value={range ? [dayjs(range[0]), dayjs(range[1])] : null}
          maxDate={dayjs(new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Yekaterinburg" }).format(new Date()))}
          disabledDate={(date, info) => Boolean(info.from && Math.abs(date.diff(info.from, "day")) >= 365)}
          onChange={dates => dates?.[0] && dates[1] ? selectPeriod(days, [dates[0].format("YYYY-MM-DD"), dates[1].format("YYYY-MM-DD")]) : selectPeriod(30)} />
        {exportAction}</Space>}
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
            <MetricLineChart
              ariaLabel={`${copy.sales}: ${copy.trend}`}
              emptyText={locale === "ru" ? "За выбранный период продаж нет" : "No sales in this period"}
              description={copy.salesTrendExplanation}
              data={data.sales.trend.map((point) => ({ key: point.date, label: dayjs(point.date).format("DD.MM"), tooltipLabel: dayjs(point.date).format("DD.MM.YYYY"), values: { revenue: Number(point.revenue), orders: point.orders } }))}
              series={[
                { key: "revenue", label: copy.revenue, color: "#0f766e", formatValue: (value) => money(value, "RUB", locale) },
                { key: "orders", label: copy.paidOrders, color: "#6366f1", axis: "right", formatValue: (value) => new Intl.NumberFormat(locale === "ru" ? "ru-RU" : "en-US").format(value) },
              ]}
              leftAxisFormatter={(value) => new Intl.NumberFormat(locale === "ru" ? "ru-RU" : "en-US", { notation: "compact", maximumFractionDigits: 1 }).format(value)}
            />
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
            <MetricLineChart
              ariaLabel={copy.appOpens}
              emptyText={copy.noOpens}
              description={copy.opensExplanation}
              data={openTrend.map((point) => ({ key: point.period, label: dayjs(point.period).format(openGranularity === "daily" ? "DD.MM" : "MM.YYYY"), tooltipLabel: dayjs(point.period).format(openGranularity === "daily" ? "DD.MM.YYYY" : "MM.YYYY"), values: { opens: point.opens, customers: point.customers } }))}
              series={[
                { key: "opens", label: copy.appOpens, color: "#6366f1" },
                { key: "customers", label: copy.uniqueCustomers, color: "#0f766e" },
              ]}
            />
          </Card>
          <Card title={<Space><LineChartOutlined />{authTitle}</Space>}>
            <MetricLineChart ariaLabel={authTitle}
              emptyText={locale === "ru" ? "За эти даты учёт ещё не вёлся" : "No tracking data for these dates"}
              description={locale === "ru"
                ? "Регистрация считается один раз, входы считаются отдельно. Даты по Уфе. Прочерк: учёт ещё не вёлся. Первый день учёта может быть неполным."
                : "Registration counts once; sign-ins count separately. Dates use Ufa time. A dash means no tracking data; the first tracked day may be partial."}
              data={dailyAuth.flatMap(p => p.registrations === null || p.logins === null ? [] : [{
                key: p.date, label: dayjs(p.date).format("DD.MM"), tooltipLabel: dayjs(p.date).format("DD.MM.YYYY"),
                values: { registrations: p.registrations, logins: p.logins },
              }])}
              series={[{ key: "registrations", label: registrationLabel, color: "#6366f1" }, { key: "logins", label: signInLabel, color: "#0f766e" }]} />
            <Table rowKey="date" size="small" dataSource={[...dailyAuth].reverse()} pagination={{ pageSize: 7, showSizeChanger: false }}
              columns={[
                { title: locale === "ru" ? "Дата" : "Date", dataIndex: "date", render: value => dayjs(value).format("DD.MM.YYYY") },
                { title: registrationLabel, dataIndex: "registrations", align: "right", render: n => n ?? "—" },
                { title: signInLabel, dataIndex: "logins", align: "right", render: n => n ?? "—" },
              ]} />
          </Card>
          <Table rowKey="user_id" dataSource={data.customers.top_customers} pagination={{ pageSize: 10 }} columns={[{ title: copy.customers, render: (_: unknown, row) => <div className="table-primary">{hasPermission("customers.read") ? <Link to={`/customers/${row.user_id}`}><strong>{row.name}</strong></Link> : <strong>{row.name}</strong>}<small>{row.email || `#${row.user_id}`}</small></div> }, { title: copy.orders, dataIndex: "orders", align: "right" }, { title: copy.ltv, dataIndex: "ltv", render: (value: string) => money(value, "RUB", locale) }]} />
          <Row gutter={[16, 16]} className="analytics-device-grid">
            <Col xs={24} lg={8}>
              <Card title={locale === "ru" ? "Платформы" : "Platforms"}>
                <Table rowKey="platform" size="small" dataSource={data.customers.devices.platforms} pagination={false} columns={[{ title: locale === "ru" ? "Платформа" : "Platform", dataIndex: "platform", render: (value: string) => <Tag>{domainLabel(value, locale)}</Tag> }, { title: copy.customers, dataIndex: "customers", align: "right" }]} />
              </Card>
            </Col>
            <Col xs={24} lg={8}>
              <Card title={locale === "ru" ? "Версии приложения" : "App versions"}>
                <Table rowKey={(row) => `${row.platform}-${row.app_version}`} size="small" dataSource={data.customers.devices.app_versions} pagination={data.customers.devices.app_versions.length > 8 ? { pageSize: 8, showSizeChanger: false } : false} columns={[{ title: locale === "ru" ? "Версия" : "Version", render: (_: unknown, row) => <Space><Tag>{domainLabel(row.platform, locale)}</Tag>{row.app_version}</Space> }, { title: copy.customers, dataIndex: "customers", align: "right" }]} />
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
