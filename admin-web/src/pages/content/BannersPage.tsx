import { EditOutlined, PlusOutlined, UploadOutlined } from "@ant-design/icons"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Button, Card, Form, Image, Input, InputNumber, Modal, Select, Space, Table, Tag, Upload, message } from "antd"
import { useEffect, useState } from "react"
import { apiRequest } from "../../api/client"
import type { Banner, BannerUpload, Page } from "../../api/types"
import { PageHeader } from "../../components/PageHeader"
import { useLanguage } from "../../i18n/LanguageProvider"
import { dateTime } from "../../utils/format"

type BannerForm = {
  image_path: string | null
  desktop_image_path: string | null
  mobile_image_path: string | null
  title: string | null
  inner_link: string | null
  outer_link: string | null
  priority: number
  archived: boolean
  status: Banner["status"]
  starts_at: string | null
  ends_at: string | null
  audience_json_text: string
}

type UploadOptions = {
  file: string | Blob
  onSuccess?: (body: unknown) => void
  onError?: (error: Error) => void
}

const emptyBanner: BannerForm = {
  image_path: "",
  desktop_image_path: "",
  mobile_image_path: "",
  title: "",
  inner_link: "",
  outer_link: "",
  priority: 0,
  archived: false,
  status: "draft",
  starts_at: null,
  ends_at: null,
  audience_json_text: "{}",
}

function toLocalInputValue(value: string | null) {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  const offset = date.getTimezoneOffset()
  return new Date(date.getTime() - offset * 60_000).toISOString().slice(0, 16)
}

function toIsoOrNull(value: string | null | undefined) {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date.toISOString()
}

function parseJsonObject(value: string) {
  const parsed = JSON.parse(value || "{}") as unknown
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error("Audience must be a JSON object")
  return parsed as Record<string, unknown>
}

export function BannersPage() {
  const { locale } = useLanguage()
  const client = useQueryClient()
  const [editing, setEditing] = useState<Banner | "new" | null>(null)
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const [form] = Form.useForm<BannerForm>()
  const values = Form.useWatch([], form)
  const copy = locale === "ru"
    ? {
      title: "Баннеры", description: "Минималистичные промо-блоки витрины: draft, расписание, preview и клики.", add: "Добавить", image: "Основное изображение",
      desktop: "Desktop изображение", mobile: "Mobile изображение", upload: "Загрузить", bannerTitle: "Заголовок", inner: "Внутренняя ссылка", outer: "Внешняя ссылка",
      priority: "Приоритет", state: "Статус", updated: "Обновлено", edit: "Редактировать", save: "Сохранить", schedule: "Расписание", starts: "Старт", ends: "Финиш",
      audience: "Аудитория JSON", clicks: "Клики", impressions: "Показы", preview: "Preview", all: "Все статусы", saved: "Баннер сохранён", draft: "Черновик",
      scheduled: "Запланирован", published: "Опубликован", archived: "Архив",
    }
    : {
      title: "Banners", description: "Minimal storefront promos: draft state, scheduling, preview and click tracking.", add: "Add", image: "Main image",
      desktop: "Desktop image", mobile: "Mobile image", upload: "Upload", bannerTitle: "Title", inner: "Internal link", outer: "External link",
      priority: "Priority", state: "Status", updated: "Updated", edit: "Edit", save: "Save", schedule: "Schedule", starts: "Start", ends: "End",
      audience: "Audience JSON", clicks: "Clicks", impressions: "Impressions", preview: "Preview", all: "All statuses", saved: "Banner saved", draft: "Draft",
      scheduled: "Scheduled", published: "Published", archived: "Archived",
    }

  const query = useQuery({ queryKey: ["banners", statusFilter], queryFn: () => apiRequest<Page<Banner>>(`/banners?limit=100${statusFilter ? `&status=${statusFilter}` : ""}`) })
  useEffect(() => {
    if (editing === "new") form.setFieldsValue(emptyBanner)
    else if (editing) {
      form.setFieldsValue({
        image_path: editing.image_path,
        desktop_image_path: editing.desktop_image_path,
        mobile_image_path: editing.mobile_image_path,
        title: editing.title,
        inner_link: editing.inner_link,
        outer_link: editing.outer_link,
        priority: editing.priority,
        archived: editing.archived,
        status: editing.status,
        starts_at: toLocalInputValue(editing.starts_at),
        ends_at: toLocalInputValue(editing.ends_at),
        audience_json_text: JSON.stringify(editing.audience_json || {}, null, 2),
      })
    }
  }, [editing, form])

  const uploadImage = (field: "image_path" | "desktop_image_path" | "mobile_image_path") => async (options: UploadOptions) => {
    const body = new FormData()
    body.append("file", options.file as File)
    try {
      const result = await apiRequest<BannerUpload>("/banners/upload", { method: "POST", body })
      form.setFieldValue(field, result.image_path)
      options.onSuccess?.(result)
    } catch (error) {
      options.onError?.(error as Error)
      void message.error((error as Error).message)
    }
  }

  const mutation = useMutation({
    mutationFn: (rawValues: BannerForm) => {
      const audience_json = parseJsonObject(rawValues.audience_json_text)
      const payload = {
        image_path: rawValues.image_path || rawValues.desktop_image_path || rawValues.mobile_image_path,
        desktop_image_path: rawValues.desktop_image_path || null,
        mobile_image_path: rawValues.mobile_image_path || null,
        title: rawValues.title || null,
        inner_link: rawValues.inner_link || null,
        outer_link: rawValues.outer_link || null,
        priority: rawValues.priority ?? 0,
        archived: rawValues.status === "archived",
        status: rawValues.status,
        starts_at: toIsoOrNull(rawValues.starts_at),
        ends_at: toIsoOrNull(rawValues.ends_at),
        audience_json,
      }
      return apiRequest<Banner>(editing === "new" ? "/banners" : `/banners/${editing?.id}`, {
        method: editing === "new" ? "POST" : "PUT",
        body: JSON.stringify(editing === "new" ? payload : { ...payload, expected_updated_at: editing?.updated_at }),
      })
    },
    onSuccess: () => {
      setEditing(null)
      void client.invalidateQueries({ queryKey: ["banners"] })
      void message.success(copy.saved)
    },
    onError: (error: Error) => void message.error(error.message),
  })

  const statusLabels = { draft: copy.draft, scheduled: copy.scheduled, published: copy.published, archived: copy.archived }
  const statusColors = { draft: "default", scheduled: "blue", published: "green", archived: "default" }
  const previewSource = values?.desktop_image_path || values?.image_path || values?.mobile_image_path || null

  return <div className="page-stack">
    <PageHeader title={copy.title} description={copy.description} actions={<Button type="primary" icon={<PlusOutlined />} onClick={() => setEditing("new")}>{copy.add}</Button>} />
    <Card className="filter-card">
      <Select allowClear value={statusFilter} placeholder={copy.all} style={{ width: 210 }} options={Object.entries(statusLabels).map(([value, label]) => ({ value, label }))} onChange={setStatusFilter} />
    </Card>
    <Table<Banner> rowKey="id" loading={query.isLoading} dataSource={query.data?.items} pagination={false} columns={[
      { title: copy.preview, dataIndex: "image_path", render: (_: string, row) => <Image src={row.desktop_image_path || row.image_path || row.mobile_image_path || undefined} width={96} height={54} className="banner-thumb" /> },
      { title: copy.bannerTitle, dataIndex: "title", render: (value: string | null, row) => <div className="table-primary"><strong>{value || row.image_path}</strong><small>{row.inner_link || row.outer_link || "—"}</small></div> },
      { title: copy.priority, dataIndex: "priority", align: "center" },
      { title: copy.state, dataIndex: "status", render: (value: Banner["status"]) => <Tag color={statusColors[value]}>{statusLabels[value]}</Tag> },
      { title: copy.schedule, render: (_: unknown, row) => <span>{row.starts_at ? dateTime(row.starts_at, locale) : "—"} → {row.ends_at ? dateTime(row.ends_at, locale) : "—"}</span> },
      { title: copy.clicks, dataIndex: "click_count", align: "center" },
      { title: copy.updated, dataIndex: "updated_at", render: (value: string) => dateTime(value, locale) },
      { title: "", align: "right", render: (_: unknown, row) => <Button icon={<EditOutlined />} onClick={() => setEditing(row)}>{copy.edit}</Button> },
    ]} />
    <Modal width={760} open={Boolean(editing)} title={editing === "new" ? copy.add : copy.edit} okText={copy.save} confirmLoading={mutation.isPending} onCancel={() => setEditing(null)} onOk={() => void form.validateFields().then((nextValues) => mutation.mutate(nextValues))}>
      <Form form={form} layout="vertical">
        <div className="banner-form-grid">
          <div>
            <Form.Item name="title" label={copy.bannerTitle}><Input /></Form.Item>
            <Form.Item name="image_path" label={copy.image}><Input /></Form.Item>
            <Form.Item name="desktop_image_path" label={copy.desktop}>
              <Input addonAfter={<Upload showUploadList={false} accept="image/*" customRequest={uploadImage("desktop_image_path")}><Button size="small" icon={<UploadOutlined />}>{copy.upload}</Button></Upload>} />
            </Form.Item>
            <Form.Item name="mobile_image_path" label={copy.mobile}>
              <Input addonAfter={<Upload showUploadList={false} accept="image/*" customRequest={uploadImage("mobile_image_path")}><Button size="small" icon={<UploadOutlined />}>{copy.upload}</Button></Upload>} />
            </Form.Item>
            <Form.Item name="inner_link" label={copy.inner}><Input placeholder="/products/1" /></Form.Item>
            <Form.Item name="outer_link" label={copy.outer}><Input placeholder="https://…" /></Form.Item>
          </div>
          <div>
            <Card size="small" title={copy.preview} className="banner-preview-card">
              {previewSource ? <Image src={previewSource} /> : <div className="empty-preview">{copy.preview}</div>}
            </Card>
            <Space style={{ width: "100%" }} size={12}>
              <Form.Item name="priority" label={copy.priority} style={{ flex: 1 }}><InputNumber min={0} style={{ width: "100%" }} /></Form.Item>
              <Form.Item name="status" label={copy.state} style={{ flex: 1 }}><Select options={Object.entries(statusLabels).map(([value, label]) => ({ value, label }))} /></Form.Item>
            </Space>
            <Space style={{ width: "100%" }} size={12}>
              <Form.Item name="starts_at" label={copy.starts} style={{ flex: 1 }}><Input type="datetime-local" /></Form.Item>
              <Form.Item name="ends_at" label={copy.ends} style={{ flex: 1 }}><Input type="datetime-local" /></Form.Item>
            </Space>
            <Form.Item name="audience_json_text" label={copy.audience} rules={[{ validator: async (_, value) => { parseJsonObject(value || "{}") } }]}><Input.TextArea rows={7} /></Form.Item>
          </div>
        </div>
      </Form>
    </Modal>
  </div>
}
