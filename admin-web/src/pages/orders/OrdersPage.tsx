import { AppstoreOutlined, BarsOutlined, ReloadOutlined, SearchOutlined } from "@ant-design/icons"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Button, Card, Input, Segmented, Select, Space, Table, Tag, Typography, message } from "antd"
import { useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { apiRequest, queryString } from "../../api/client"
import type { OrderListItem, OrderStatusCode, Page } from "../../api/types"
import { PageHeader } from "../../components/PageHeader"
import { parseVisibleColumns, TableToolbar, type TableColumnOption } from "../../components/TableToolbar"
import { useAuth } from "../../auth/AuthProvider"
import { useLanguage } from "../../i18n/LanguageProvider"
import { dateTime, money, statusColors, statusLabel } from "../../utils/format"

const kanbanStatuses: OrderStatusCode[] = ["created", "invoice_sent", "paid", "waiting_response", "packaged", "sent", "delivered", "completed", "canceled"]

export function OrdersPage() {
  const { locale } = useLanguage()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const view = searchParams.get("view") === "kanban" ? "kanban" : "table"
  const search = searchParams.get("q") || ""
  const rawStatus = searchParams.get("status") as OrderStatusCode | null
  const status = rawStatus && kanbanStatuses.includes(rawStatus) ? rawStatus : undefined
  const page = Math.max(Number(searchParams.get("page") || 1) || 1, 1)
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const updateFilters = (values: Record<string, string | number | undefined>) => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current)
      Object.entries(values).forEach(([key, value]) => {
        if (value === undefined || value === "" || value === 1) next.delete(key)
        else next.set(key, String(value))
      })
      return next
    })
  }
  const pageSize = view === "kanban" ? 200 : 50
  const query = useQuery({
    queryKey: ["orders", search, status, page, view],
    queryFn: () => apiRequest<Page<OrderListItem>>(`/orders${queryString({ q: search, status_code: status, limit: pageSize, offset: (page - 1) * pageSize })}`),
    refetchInterval: 30_000,
  })
  const transition = useMutation({
    mutationFn: ({ order, nextStatus }: { order: OrderListItem; nextStatus: OrderStatusCode }) => apiRequest(`/orders/${order.id}/transition`, {
      method: "POST",
      body: JSON.stringify({ status_code: nextStatus, expected_updated_at: order.updated_at }),
    }),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ["orders"] }); void message.success(locale === "ru" ? "Статус обновлён" : "Status updated") },
    onError: (error: Error) => void message.error(error.message),
  })
  const copy = locale === "ru"
    ? { title: "Заказы", description: "Продажи, оплаты и доставка в одном рабочем пространстве", table: "Таблица", kanban: "Канбан", order: "Заказ", customer: "Клиент", status: "Статус", payment: "Оплата", delivery: "Доставка", total: "Сумма", created: "Создан", allStatuses: "Все статусы" }
    : { title: "Orders", description: "Sales, payments and fulfillment in one workspace", table: "Table", kanban: "Kanban", order: "Order", customer: "Customer", status: "Status", payment: "Payment", delivery: "Delivery", total: "Total", created: "Created", allStatuses: "All statuses" }

  const tableColumns = [
    { title: copy.order, dataIndex: "order_code", key: "order", render: (value: string, record: OrderListItem) => <Link to={`/sales/orders/${record.id}`}><strong>{value}</strong></Link> },
    { title: copy.customer, key: "customer", render: (_: unknown, record: OrderListItem) => <div className="table-primary"><span>{record.customer.name} {record.customer.surname}</span><small>{record.customer.phone_number || record.customer.email || "—"}</small></div> },
    { title: copy.status, dataIndex: "status_code", key: "status", render: (value: OrderStatusCode) => <Tag color={statusColors[value]}>{statusLabel(value, locale)}</Tag> },
    { title: copy.payment, key: "payment", render: (_: unknown, record: OrderListItem) => <div className="table-primary"><span>{record.payment_status}</span><small>{record.payment_method || "—"}</small></div> },
    { title: copy.delivery, dataIndex: "delivery_service", key: "delivery", render: (value: string) => value || "—" },
    { title: copy.total, key: "total", align: "right" as const, render: (_: unknown, record: OrderListItem) => <strong>{money(record.grand_total, record.currency, locale)}</strong> },
    { title: copy.created, dataIndex: "created_at", key: "created", render: (value: string) => dateTime(value, locale) },
  ]
  const columnOptions: TableColumnOption[] = [
    { key: "order", label: copy.order, exportKeys: ["order_code"] },
    { key: "customer", label: copy.customer, exportKeys: ["customer", "email", "phone"] },
    { key: "status", label: copy.status, exportKeys: ["status"] },
    { key: "payment", label: copy.payment, exportKeys: ["payment_status"] },
    { key: "delivery", label: copy.delivery, exportKeys: ["delivery_service"] },
    { key: "total", label: copy.total, exportKeys: ["grand_total"] },
    { key: "created", label: copy.created, exportKeys: ["created_at"] },
  ]
  const visibleColumns = parseVisibleColumns(searchParams.get("columns"), columnOptions.map((column) => column.key))
  const viewState = Object.fromEntries(Array.from(searchParams.entries()).filter(([key]) => key !== "page"))

  return (
    <div className="page-stack">
      <PageHeader title={copy.title} description={copy.description} actions={<Button icon={<ReloadOutlined />} onClick={() => void query.refetch()} />} />
      <Card className="filter-card">
        <Space wrap>
          <Input allowClear prefix={<SearchOutlined />} placeholder={locale === "ru" ? "Номер, имя, телефон" : "Number, name, phone"} value={search} onChange={(event) => updateFilters({ q: event.target.value, page: 1 })} />
          <Select allowClear value={status} placeholder={copy.allStatuses} style={{ minWidth: 190 }} onChange={(value) => updateFilters({ status: value, page: 1 })} options={kanbanStatuses.map((value) => ({ value, label: statusLabel(value, locale) }))} />
          <Segmented value={view} onChange={(value) => updateFilters({ view: value === "kanban" ? "kanban" : undefined, page: 1 })} options={[{ value: "table", label: copy.table, icon: <BarsOutlined /> }, { value: "kanban", label: copy.kanban, icon: <AppstoreOutlined /> }]} />
        </Space>
      </Card>
      {view === "table" ? (
        <>
          <TableToolbar
            resource="orders"
            columns={columnOptions}
            visibleColumns={visibleColumns}
            onVisibleColumnsChange={(keys) => updateFilters({ columns: keys.length === columnOptions.length ? undefined : keys.join(","), page: 1 })}
            viewState={viewState}
            onApplyViewState={(state) => { setSelectedRowKeys([]); setSearchParams(state) }}
            exportFilters={{ q: search, status_code: status }}
            selectedIds={selectedRowKeys.map(Number)}
            onClearSelection={() => setSelectedRowKeys([])}
          />
          <Table<OrderListItem>
            rowKey="id"
            loading={query.isLoading}
            dataSource={query.data?.items}
            columns={tableColumns.filter((column) => visibleColumns.includes(String(column.key)))}
            rowSelection={{ selectedRowKeys, preserveSelectedRowKeys: true, onChange: setSelectedRowKeys }}
            scroll={{ x: 1050 }}
            pagination={{ current: page, pageSize, total: query.data?.total, showSizeChanger: false, onChange: (nextPage) => updateFilters({ page: nextPage }) }}
          />
        </>
      ) : (
        <div className="kanban-board">
          {kanbanStatuses.map((columnStatus) => {
            const orders = (query.data?.items || []).filter((order) => order.status_code === columnStatus)
            return (
              <section
                className="kanban-column"
                key={columnStatus}
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => {
                  const order = query.data?.items.find((item) => item.id === Number(event.dataTransfer.getData("order-id")))
                  if (order && order.status_code !== columnStatus && hasPermission("orders.transition")) transition.mutate({ order, nextStatus: columnStatus })
                }}
              >
                <header><Tag color={statusColors[columnStatus]}>{statusLabel(columnStatus, locale)}</Tag><span>{orders.length}</span></header>
                <div className="kanban-list">
                  {orders.map((order) => (
                    <Card key={order.id} size="small" className="kanban-card" draggable={hasPermission("orders.transition")} onDragStart={(event) => event.dataTransfer.setData("order-id", String(order.id))}>
                      <Link to={`/sales/orders/${order.id}`}><Typography.Text strong>{order.order_code}</Typography.Text></Link>
                      <Typography.Text>{order.customer.name} {order.customer.surname}</Typography.Text>
                      <div><Typography.Text type="secondary">{dateTime(order.created_at, locale)}</Typography.Text><strong>{money(order.grand_total, order.currency, locale)}</strong></div>
                    </Card>
                  ))}
                </div>
              </section>
            )
          })}
        </div>
      )}
    </div>
  )
}
