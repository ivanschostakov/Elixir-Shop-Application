import { SearchOutlined } from "@ant-design/icons"
import { useQuery } from "@tanstack/react-query"
import { Avatar, Card, Input, Select, Space, Table, Tag } from "antd"
import { useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { apiRequest, queryString } from "../../api/client"
import type { CustomerListItem, Page } from "../../api/types"
import { PageHeader } from "../../components/PageHeader"
import { parseVisibleColumns, TableToolbar, type TableColumnOption } from "../../components/TableToolbar"
import { useLanguage } from "../../i18n/LanguageProvider"
import { dateTime, money } from "../../utils/format"

export function CustomersPage() {
  const { locale } = useLanguage()
  const [searchParams, setSearchParams] = useSearchParams()
  const search = searchParams.get("q") || ""
  const activeFilter = searchParams.get("active")
  const active = activeFilter === "active" ? true : activeFilter === "blocked" ? false : undefined
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
  const pageSize = 50
  const query = useQuery({ queryKey: ["customers", search, active, page], queryFn: () => apiRequest<Page<CustomerListItem>>(`/customers${queryString({ q: search, is_active: active, limit: pageSize, offset: (page - 1) * pageSize })}`) })
  const copy = locale === "ru"
    ? { title: "Клиенты", description: "Профили, история покупок и активность", search: "Имя, email или телефон", all: "Все клиенты", active: "Активные", blocked: "Заблокированные", customer: "Клиент", contact: "Контакт", orders: "Заказы", ltv: "Выручка", lastOrder: "Последний заказ", state: "Статус" }
    : { title: "Customers", description: "Profiles, purchase history and activity", search: "Name, email or phone", all: "All customers", active: "Active", blocked: "Blocked", customer: "Customer", contact: "Contact", orders: "Orders", ltv: "Revenue", lastOrder: "Last order", state: "Status" }
  const tableColumns = [
    { title: copy.customer, key: "customer", render: (_: unknown, row: CustomerListItem) => <Space><Avatar>{`${row.name[0] || ""}${row.surname[0] || ""}`}</Avatar><div className="table-primary"><Link to={`/customers/${row.id}`}><strong>{row.name} {row.surname}</strong></Link><small>ID {row.id}</small></div></Space> },
    { title: copy.contact, key: "contact", render: (_: unknown, row: CustomerListItem) => <div className="table-primary"><span>{row.phone_number || "—"}</span><small>{row.email || "—"}</small></div> },
    { title: copy.orders, dataIndex: "orders_count", key: "orders", align: "center" as const },
    { title: copy.ltv, key: "ltv", align: "right" as const, render: (_: unknown, row: CustomerListItem) => money(row.paid_total, "RUB", locale) },
    { title: copy.lastOrder, dataIndex: "last_order_at", key: "lastOrder", render: (value: string | null) => dateTime(value, locale) },
    { title: copy.state, key: "state", render: (_: unknown, row: CustomerListItem) => <Tag color={row.is_active ? "green" : "red"}>{row.is_active ? copy.active : copy.blocked}</Tag> },
  ]
  const columnOptions: TableColumnOption[] = [
    { key: "customer", label: copy.customer, exportKeys: ["customer"] },
    { key: "contact", label: copy.contact, exportKeys: ["email", "phone", "telegram"] },
    { key: "orders", label: copy.orders, exportKeys: ["orders_count"] },
    { key: "ltv", label: copy.ltv, exportKeys: ["paid_total"] },
    { key: "lastOrder", label: copy.lastOrder, exportKeys: ["last_order_at"] },
    { key: "state", label: copy.state, exportKeys: ["is_active", "is_verified"] },
  ]
  const visibleColumns = parseVisibleColumns(searchParams.get("columns"), columnOptions.map((column) => column.key))
  const viewState = Object.fromEntries(Array.from(searchParams.entries()).filter(([key]) => key !== "page"))

  return (
    <div className="page-stack">
      <PageHeader title={copy.title} description={copy.description} />
      <Card className="filter-card"><Space wrap>
        <Input allowClear prefix={<SearchOutlined />} placeholder={copy.search} value={search} onChange={(event) => updateFilters({ q: event.target.value, page: 1 })} />
        <Select value={active === undefined ? "all" : active ? "active" : "blocked"} style={{ width: 180 }} onChange={(value) => updateFilters({ active: value === "all" ? undefined : value, page: 1 })} options={[{ value: "all", label: copy.all }, { value: "active", label: copy.active }, { value: "blocked", label: copy.blocked }]} />
      </Space></Card>
      <TableToolbar
        resource="customers"
        columns={columnOptions}
        visibleColumns={visibleColumns}
        onVisibleColumnsChange={(keys) => updateFilters({ columns: keys.length === columnOptions.length ? undefined : keys.join(","), page: 1 })}
        viewState={viewState}
        onApplyViewState={(state) => { setSelectedRowKeys([]); setSearchParams(state) }}
        exportFilters={{ q: search, is_active: active }}
        selectedIds={selectedRowKeys.map(Number)}
        onClearSelection={() => setSelectedRowKeys([])}
      />
      <Table<CustomerListItem>
        rowKey="id"
        loading={query.isLoading}
        dataSource={query.data?.items}
        rowSelection={{ selectedRowKeys, preserveSelectedRowKeys: true, onChange: setSelectedRowKeys }}
        pagination={{ current: page, pageSize, total: query.data?.total, showSizeChanger: false, onChange: (nextPage) => updateFilters({ page: nextPage }) }}
        columns={tableColumns.filter((column) => visibleColumns.includes(String(column.key)))}
      />
    </div>
  )
}
