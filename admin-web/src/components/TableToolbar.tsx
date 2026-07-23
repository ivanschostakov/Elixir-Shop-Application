import {
  CheckOutlined,
  CloudDownloadOutlined,
  DeleteOutlined,
  DownOutlined,
  SaveOutlined,
  SettingOutlined,
} from "@ant-design/icons"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Button, Checkbox, Dropdown, Input, Modal, Select, Space, Tooltip, Typography, message } from "antd"
import { useMemo, useState, type ReactNode } from "react"
import { apiDownload, apiRequest, queryString } from "../api/client"
import type { AdminExport, SavedView } from "../api/types"
import { useAuth } from "../auth/AuthProvider"
import { useLanguage } from "../i18n/LanguageProvider"

export type TableColumnOption = {
  key: string
  label: string
  exportKeys?: string[]
}

type TableToolbarProps = {
  resource: "orders" | "customers" | "products" | "reviews" | "audit"
  columns: TableColumnOption[]
  visibleColumns: string[]
  onVisibleColumnsChange: (columns: string[]) => void
  viewState: Record<string, string>
  onApplyViewState: (state: Record<string, string>) => void
  exportFilters: Record<string, string | number | boolean | null | undefined>
  selectedIds?: number[]
  selectedCount?: number
  onClearSelection?: () => void
  bulkActions?: ReactNode
}

const TERMINAL_EXPORT_STATUSES = new Set(["success", "error"])

function cleanSavedState(value: Record<string, unknown>): Record<string, string> {
  return Object.fromEntries(
    Object.entries(value).filter((entry): entry is [string, string] => typeof entry[1] === "string"),
  )
}

function triggerDownload(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = fileName
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

async function waitForExport(run: AdminExport): Promise<AdminExport> {
  let current = run
  for (let attempt = 0; attempt < 120 && !TERMINAL_EXPORT_STATUSES.has(current.status); attempt += 1) {
    await new Promise((resolve) => window.setTimeout(resolve, 1000))
    current = await apiRequest<AdminExport>(`/exports/${run.id}`)
  }
  if (!TERMINAL_EXPORT_STATUSES.has(current.status)) throw new Error("Export timed out")
  if (current.status === "error") throw new Error(current.error || "Export failed")
  return current
}

export function parseVisibleColumns(value: string | null, allowed: string[]) {
  if (!value) return allowed
  const parsed = value.split(",").filter((key) => allowed.includes(key))
  return parsed.length ? Array.from(new Set(parsed)) : allowed
}

export function TableToolbar({
  resource,
  columns,
  visibleColumns,
  onVisibleColumnsChange,
  viewState,
  onApplyViewState,
  exportFilters,
  selectedIds = [],
  selectedCount = selectedIds.length,
  onClearSelection,
  bulkActions,
}: TableToolbarProps) {
  const { locale } = useLanguage()
  const { principal, hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const [activeViewId, setActiveViewId] = useState<number>()
  const [saveOpen, setSaveOpen] = useState(false)
  const [viewName, setViewName] = useState("")
  const [isShared, setIsShared] = useState(false)
  const copy = locale === "ru"
    ? { view: "Представление", saveView: "Сохранить вид", name: "Название представления", shared: "Доступно команде", columns: "Колонки", export: "Экспорт", selected: "Выбрано", clear: "Снять выбор", saved: "Представление сохранено", deleted: "Представление удалено", downloaded: "Выгрузка готова", csv: "CSV", xlsx: "Excel (.xlsx)", create: "Создать" }
    : { view: "View", saveView: "Save view", name: "View name", shared: "Share with team", columns: "Columns", export: "Export", selected: "Selected", clear: "Clear", saved: "View saved", deleted: "View deleted", downloaded: "Export ready", csv: "CSV", xlsx: "Excel (.xlsx)", create: "Create" }

  const views = useQuery({
    queryKey: ["saved-views", resource],
    queryFn: () => apiRequest<SavedView[]>(`/saved-views${queryString({ resource })}`),
  })
  const activeView = views.data?.find((view) => view.id === activeViewId)

  const saveView = useMutation({
    mutationFn: () => apiRequest<SavedView>("/saved-views", {
      method: "POST",
      body: JSON.stringify({ resource, name: viewName.trim(), state_json: viewState, is_shared: isShared }),
    }),
    onSuccess: (view) => {
      setActiveViewId(view.id)
      setSaveOpen(false)
      setViewName("")
      setIsShared(false)
      void queryClient.invalidateQueries({ queryKey: ["saved-views", resource] })
      void message.success(copy.saved)
    },
    onError: (error: Error) => void message.error(error.message),
  })
  const updateView = useMutation({
    mutationFn: (view: SavedView) => apiRequest<SavedView>(`/saved-views/${view.id}`, {
      method: "PUT",
      body: JSON.stringify({ resource, name: view.name, state_json: viewState, is_shared: view.is_shared }),
    }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["saved-views", resource] })
      void message.success(copy.saved)
    },
    onError: (error: Error) => void message.error(error.message),
  })
  const deleteView = useMutation({
    mutationFn: (viewId: number) => apiRequest<void>(`/saved-views/${viewId}`, { method: "DELETE" }),
    onSuccess: () => {
      setActiveViewId(undefined)
      void queryClient.invalidateQueries({ queryKey: ["saved-views", resource] })
      void message.success(copy.deleted)
    },
    onError: (error: Error) => void message.error(error.message),
  })

  const exportColumns = useMemo(
    () => columns.filter((column) => visibleColumns.includes(column.key)).flatMap((column) => column.exportKeys || []),
    [columns, visibleColumns],
  )
  const exportMutation = useMutation({
    mutationFn: async (format: "csv" | "xlsx") => {
      const run = await apiRequest<AdminExport>("/exports", {
        method: "POST",
        body: JSON.stringify({
          resource,
          format,
          columns: exportColumns,
          filters: Object.fromEntries(Object.entries(exportFilters).filter(([, value]) => value !== undefined && value !== null && value !== "")),
          selected_ids: selectedIds,
          locale,
          idempotency_key: crypto.randomUUID(),
        }),
      })
      const ready = await waitForExport(run)
      const file = await apiDownload(`/exports/${ready.id}/download`)
      triggerDownload(file.blob, file.fileName || `${resource}.${format}`)
      return ready
    },
    onSuccess: (run) => void message.success(`${copy.downloaded}${run.rows === null ? "" : ` · ${run.rows}`}`),
    onError: (error: Error) => void message.error(error.message),
  })

  const columnMenu = {
    items: [{
      key: "columns",
      label: (
        <Checkbox.Group
          className="table-column-picker"
          value={visibleColumns}
          options={columns.map((column) => ({ label: column.label, value: column.key }))}
          onChange={(values) => { if (values.length) onVisibleColumnsChange(values as string[]) }}
        />
      ),
    }],
  }
  const exportMenu = {
    items: [
      { key: "csv", label: copy.csv, onClick: () => exportMutation.mutate("csv" as const) },
      { key: "xlsx", label: copy.xlsx, onClick: () => exportMutation.mutate("xlsx" as const) },
    ],
  }

  return (
    <div className={`table-toolbar${selectedCount ? " has-selection" : ""}`}>
      <Space wrap size={8}>
        <Select
          allowClear
          loading={views.isLoading}
          placeholder={copy.view}
          value={activeViewId}
          style={{ minWidth: 180 }}
          options={(views.data || []).map((view) => ({
            value: view.id,
            label: view.is_shared ? `${view.name} · team` : view.name,
          }))}
          onClear={() => setActiveViewId(undefined)}
          onChange={(viewId) => {
            setActiveViewId(viewId)
            const view = views.data?.find((item) => item.id === viewId)
            if (view) onApplyViewState(cleanSavedState(view.state_json))
          }}
        />
        <Tooltip title={activeView && activeView.owner_user_id === principal?.user.id ? copy.saveView : copy.create}>
          <Button
            icon={<SaveOutlined />}
            loading={saveView.isPending || updateView.isPending}
            onClick={() => activeView && activeView.owner_user_id === principal?.user.id ? updateView.mutate(activeView) : setSaveOpen(true)}
          />
        </Tooltip>
        {activeView && activeView.owner_user_id === principal?.user.id ? (
          <Tooltip title={copy.deleted}><Button danger type="text" icon={<DeleteOutlined />} loading={deleteView.isPending} onClick={() => deleteView.mutate(activeView.id)} /></Tooltip>
        ) : null}
      </Space>

      {selectedCount ? (
        <Space wrap className="table-selection-actions">
          <Typography.Text strong>{copy.selected}: {selectedCount}</Typography.Text>
          {bulkActions}
          {onClearSelection ? <Button type="text" onClick={onClearSelection}>{copy.clear}</Button> : null}
        </Space>
      ) : null}

      <Space size={8} className="table-toolbar-actions">
        <Dropdown menu={columnMenu} trigger={["click"]} placement="bottomRight">
          <Button icon={<SettingOutlined />}>{copy.columns}</Button>
        </Dropdown>
        {hasPermission("exports.read") && exportColumns.length ? (
          <Dropdown menu={exportMenu} trigger={["click"]} placement="bottomRight" disabled={exportMutation.isPending}>
            <Button loading={exportMutation.isPending} icon={<CloudDownloadOutlined />}>{copy.export}<DownOutlined /></Button>
          </Dropdown>
        ) : null}
      </Space>

      <Modal
        open={saveOpen}
        title={copy.saveView}
        okText={copy.create}
        okButtonProps={{ icon: <CheckOutlined />, disabled: !viewName.trim(), loading: saveView.isPending }}
        onOk={() => saveView.mutate()}
        onCancel={() => setSaveOpen(false)}
      >
        <Space direction="vertical" size={14} style={{ width: "100%" }}>
          <Input autoFocus maxLength={120} placeholder={copy.name} value={viewName} onChange={(event) => setViewName(event.target.value)} />
          <Checkbox checked={isShared} onChange={(event) => setIsShared(event.target.checked)}>{copy.shared}</Checkbox>
        </Space>
      </Modal>
    </div>
  )
}
