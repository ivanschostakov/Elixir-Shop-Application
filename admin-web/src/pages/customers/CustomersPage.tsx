import { SearchOutlined } from "@ant-design/icons"
import { useQuery } from "@tanstack/react-query"
import { Avatar, Card, Input, Select, Space, Table, Tag } from "antd"
import { useState } from "react"
import { Link } from "react-router-dom"
import { apiRequest, queryString } from "../../api/client"
import type { CustomerListItem, Page } from "../../api/types"
import { PageHeader } from "../../components/PageHeader"
import { useLanguage } from "../../i18n/LanguageProvider"
import { dateTime, money } from "../../utils/format"

export function CustomersPage() {
  const { locale } = useLanguage()
  const [search, setSearch] = useState("")
  const [active, setActive] = useState<boolean | undefined>()
  const [page, setPage] = useState(1)
  const pageSize = 50
  const query = useQuery({ queryKey: ["customers", search, active, page], queryFn: () => apiRequest<Page<CustomerListItem>>(`/customers${queryString({ q: search, is_active: active, limit: pageSize, offset: (page - 1) * pageSize })}`) })
  const copy = locale === "ru"
    ? { title: "Клиенты", description: "Профили, история покупок и активность", search: "Имя, email или телефон", all: "Все клиенты", active: "Активные", blocked: "Заблокированные", customer: "Клиент", contact: "Контакт", orders: "Заказы", ltv: "Выручка", lastOrder: "Последний заказ", state: "Статус" }
    : { title: "Customers", description: "Profiles, purchase history and activity", search: "Name, email or phone", all: "All customers", active: "Active", blocked: "Blocked", customer: "Customer", contact: "Contact", orders: "Orders", ltv: "Revenue", lastOrder: "Last order", state: "Status" }

  return (
    <div className="page-stack">
      <PageHeader title={copy.title} description={copy.description} />
      <Card className="filter-card"><Space wrap>
        <Input allowClear prefix={<SearchOutlined />} placeholder={copy.search} value={search} onChange={(event) => { setSearch(event.target.value); setPage(1) }} />
        <Select value={active === undefined ? "all" : active ? "active" : "blocked"} style={{ width: 180 }} onChange={(value) => { setActive(value === "all" ? undefined : value === "active"); setPage(1) }} options={[{ value: "all", label: copy.all }, { value: "active", label: copy.active }, { value: "blocked", label: copy.blocked }]} />
      </Space></Card>
      <Table<CustomerListItem>
        rowKey="id"
        loading={query.isLoading}
        dataSource={query.data?.items}
        pagination={{ current: page, pageSize, total: query.data?.total, showSizeChanger: false, onChange: setPage }}
        columns={[
          { title: copy.customer, key: "customer", render: (_: unknown, row) => <Space><Avatar>{`${row.name[0] || ""}${row.surname[0] || ""}`}</Avatar><div className="table-primary"><Link to={`/customers/${row.id}`}><strong>{row.name} {row.surname}</strong></Link><small>ID {row.id}</small></div></Space> },
          { title: copy.contact, key: "contact", render: (_: unknown, row) => <div className="table-primary"><span>{row.phone_number || "—"}</span><small>{row.email || "—"}</small></div> },
          { title: copy.orders, dataIndex: "orders_count", align: "center" },
          { title: copy.ltv, key: "paid_total", align: "right", render: (_: unknown, row) => money(row.paid_total, "RUB", locale) },
          { title: copy.lastOrder, dataIndex: "last_order_at", render: (value: string | null) => dateTime(value, locale) },
          { title: copy.state, key: "state", render: (_: unknown, row) => <Tag color={row.is_active ? "green" : "red"}>{row.is_active ? copy.active : copy.blocked}</Tag> },
        ]}
      />
    </div>
  )
}
