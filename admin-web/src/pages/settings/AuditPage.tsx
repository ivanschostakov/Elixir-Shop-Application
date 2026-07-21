import { SearchOutlined } from "@ant-design/icons"
import { useQuery } from "@tanstack/react-query"
import { Card, Input, Table, Tag, Typography } from "antd"
import { useState } from "react"
import { apiRequest, queryString } from "../../api/client"
import type { AuditLog, Page } from "../../api/types"
import { PageHeader } from "../../components/PageHeader"
import { useLanguage } from "../../i18n/LanguageProvider"
import { dateTime } from "../../utils/format"

export function AuditPage() {
  const { locale } = useLanguage()
  const [search, setSearch] = useState("")
  const [page, setPage] = useState(1)
  const pageSize = 50
  const query = useQuery({ queryKey: ["audit", search, page], queryFn: () => apiRequest<Page<AuditLog>>(`/audit${queryString({ q: search, limit: pageSize, offset: (page - 1) * pageSize })}`) })
  const copy = locale === "ru" ? { title: "Журнал действий", description: "Неизменяемая история административных операций", search: "Действие или ID сущности", time: "Время", actor: "Сотрудник", action: "Действие", entity: "Объект", ip: "IP", details: "Изменения" } : { title: "Audit log", description: "Immutable history of administrative operations", search: "Action or entity ID", time: "Time", actor: "Staff member", action: "Action", entity: "Entity", ip: "IP", details: "Changes" }
  return <div className="page-stack">
    <PageHeader title={copy.title} description={copy.description} />
    <Card className="filter-card"><Input allowClear prefix={<SearchOutlined />} placeholder={copy.search} value={search} onChange={(event) => { setSearch(event.target.value); setPage(1) }} /></Card>
    <Table<AuditLog> rowKey="id" loading={query.isLoading} dataSource={query.data?.items} pagination={{ current: page, pageSize, total: query.data?.total, showSizeChanger: false, onChange: setPage }} expandable={{ expandedRowRender: (row) => <div className="audit-diff"><div><Typography.Text type="secondary">Before</Typography.Text><pre>{JSON.stringify(row.before_json, null, 2)}</pre></div><div><Typography.Text type="secondary">After</Typography.Text><pre>{JSON.stringify(row.after_json, null, 2)}</pre></div></div> }} columns={[
      { title: copy.time, dataIndex: "created_at", render: (value: string) => dateTime(value, locale) },
      { title: copy.actor, dataIndex: "actor_name" },
      { title: copy.action, dataIndex: "action", render: (value: string) => <Tag>{value}</Tag> },
      { title: copy.entity, render: (_: unknown, row) => `${row.entity_type}${row.entity_id ? ` #${row.entity_id}` : ""}` },
      { title: copy.ip, dataIndex: "ip_address", render: (value: string | null) => value || "—" },
    ]} />
  </div>
}
