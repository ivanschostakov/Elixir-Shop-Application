import { SearchOutlined } from "@ant-design/icons"
import { useQuery } from "@tanstack/react-query"
import { Card, Input, Table, Tag, Typography } from "antd"
import { useState } from "react"
import { useSearchParams } from "react-router-dom"
import { apiRequest, queryString } from "../../api/client"
import type { AuditLog, Page } from "../../api/types"
import { PageHeader } from "../../components/PageHeader"
import { parseVisibleColumns, TableToolbar, type TableColumnOption } from "../../components/TableToolbar"
import { useLanguage } from "../../i18n/LanguageProvider"
import { dateTime } from "../../utils/format"

export function AuditPage() {
  const { locale } = useLanguage()
  const [searchParams, setSearchParams] = useSearchParams()
  const search = searchParams.get("q") || ""
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
  const query = useQuery({ queryKey: ["audit", search, page], queryFn: () => apiRequest<Page<AuditLog>>(`/audit${queryString({ q: search, limit: pageSize, offset: (page - 1) * pageSize })}`) })
  const copy = locale === "ru" ? { title: "Журнал действий", description: "Неизменяемая история административных операций", search: "Действие или ID сущности", time: "Время", actor: "Сотрудник", action: "Действие", entity: "Объект", ip: "IP", details: "Изменения" } : { title: "Audit log", description: "Immutable history of administrative operations", search: "Action or entity ID", time: "Time", actor: "Staff member", action: "Action", entity: "Entity", ip: "IP", details: "Changes" }
  const tableColumns = [
    { title: copy.time, dataIndex: "created_at", key: "time", render: (value: string) => dateTime(value, locale) },
    { title: copy.actor, dataIndex: "actor_name", key: "actor" },
    { title: copy.action, dataIndex: "action", key: "action", render: (value: string) => <Tag>{value}</Tag> },
    { title: copy.entity, key: "entity", render: (_: unknown, row: AuditLog) => `${row.entity_type}${row.entity_id ? ` #${row.entity_id}` : ""}` },
    { title: copy.ip, dataIndex: "ip_address", key: "ip", render: (value: string | null) => value || "—" },
  ]
  const columnOptions: TableColumnOption[] = [
    { key: "time", label: copy.time, exportKeys: ["created_at"] },
    { key: "actor", label: copy.actor, exportKeys: ["actor"] },
    { key: "action", label: copy.action, exportKeys: ["action"] },
    { key: "entity", label: copy.entity, exportKeys: ["entity_type", "entity_id"] },
    { key: "ip", label: copy.ip, exportKeys: ["ip", "request_id"] },
  ]
  const visibleColumns = parseVisibleColumns(searchParams.get("columns"), columnOptions.map((column) => column.key))
  const viewState = Object.fromEntries(Array.from(searchParams.entries()).filter(([key]) => key !== "page"))
  return <div className="page-stack">
    <PageHeader title={copy.title} description={copy.description} />
    <Card className="filter-card"><Input allowClear prefix={<SearchOutlined />} placeholder={copy.search} value={search} onChange={(event) => updateFilters({ q: event.target.value, page: 1 })} /></Card>
    <TableToolbar
      resource="audit"
      columns={columnOptions}
      visibleColumns={visibleColumns}
      onVisibleColumnsChange={(keys) => updateFilters({ columns: keys.length === columnOptions.length ? undefined : keys.join(","), page: 1 })}
      viewState={viewState}
      onApplyViewState={(state) => { setSelectedRowKeys([]); setSearchParams(state) }}
      exportFilters={{ q: search }}
      selectedIds={selectedRowKeys.map(Number)}
      onClearSelection={() => setSelectedRowKeys([])}
    />
    <Table<AuditLog>
      rowKey="id"
      loading={query.isLoading}
      dataSource={query.data?.items}
      rowSelection={{ selectedRowKeys, preserveSelectedRowKeys: true, onChange: setSelectedRowKeys }}
      pagination={{ current: page, pageSize, total: query.data?.total, showSizeChanger: false, onChange: (nextPage) => updateFilters({ page: nextPage }) }}
      expandable={{ expandedRowRender: (row) => <div className="audit-diff"><div><Typography.Text type="secondary">Before</Typography.Text><pre>{JSON.stringify(row.before_json, null, 2)}</pre></div><div><Typography.Text type="secondary">After</Typography.Text><pre>{JSON.stringify(row.after_json, null, 2)}</pre></div></div> }}
      columns={tableColumns.filter((column) => visibleColumns.includes(String(column.key)))}
    />
  </div>
}
