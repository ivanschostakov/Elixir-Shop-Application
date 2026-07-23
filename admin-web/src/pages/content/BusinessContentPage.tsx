import { EditOutlined, HistoryOutlined } from "@ant-design/icons"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Button, Card, Drawer, Form, Input, List, Select, Space, Table, Tabs, Tag, Typography, message } from "antd"
import { useEffect, useState } from "react"
import { apiRequest } from "../../api/client"
import type { BusinessContent, BusinessContentVersion, Page } from "../../api/types"
import { PageHeader } from "../../components/PageHeader"
import { useLanguage } from "../../i18n/LanguageProvider"
import { dateTime } from "../../utils/format"

type BusinessContentForm = {
  title_ru: string
  title_en: string
  body_ru: string
  body_en: string
  link_url: string | null
  status: BusinessContent["status"]
  metadata_json_text: string
}

function parseJsonObject(value: string) {
  const parsed = JSON.parse(value || "{}") as unknown
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error("Metadata must be a JSON object")
  return parsed as Record<string, unknown>
}

export function BusinessContentPage() {
  const { locale } = useLanguage()
  const client = useQueryClient()
  const [editing, setEditing] = useState<BusinessContent | null>(null)
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const [form] = Form.useForm<BusinessContentForm>()
  const copy = locale === "ru"
    ? {
      title: "Юр. и бизнес-контент", description: "Реквизиты, контакты, доставка, оплата, privacy/terms и служебные уведомления с версионностью.",
      code: "Код", ru: "RU", en: "EN", status: "Статус", version: "Версия", updated: "Обновлено", updatedBy: "Автор", edit: "Редактировать",
      save: "Сохранить", link: "Ссылка", metadata: "Metadata JSON", history: "История версий", all: "Все статусы", draft: "Черновик",
      published: "Опубликовано", archived: "Архив", saved: "Контент сохранён", bodyRu: "Текст RU", bodyEn: "Текст EN",
    }
    : {
      title: "Legal & business content", description: "Company details, contacts, delivery, payment, privacy/terms and notices with version history.",
      code: "Code", ru: "RU", en: "EN", status: "Status", version: "Version", updated: "Updated", updatedBy: "Author", edit: "Edit",
      save: "Save", link: "Link", metadata: "Metadata JSON", history: "Version history", all: "All statuses", draft: "Draft",
      published: "Published", archived: "Archived", saved: "Content saved", bodyRu: "RU body", bodyEn: "EN body",
    }
  const statusLabels = { draft: copy.draft, published: copy.published, archived: copy.archived }
  const statusColors = { draft: "default", published: "green", archived: "default" }
  const query = useQuery({
    queryKey: ["business-content", statusFilter],
    queryFn: () => apiRequest<Page<BusinessContent>>(`/business-content?limit=100${statusFilter ? `&status=${statusFilter}` : ""}`),
  })
  const versions = useQuery({
    queryKey: ["business-content-versions", editing?.code],
    queryFn: () => apiRequest<BusinessContentVersion[]>(`/business-content/${editing?.code}/versions`),
    enabled: Boolean(editing),
  })

  useEffect(() => {
    if (!editing) return
    form.setFieldsValue({
      title_ru: editing.title_ru,
      title_en: editing.title_en,
      body_ru: editing.body_ru,
      body_en: editing.body_en,
      link_url: editing.link_url,
      status: editing.status,
      metadata_json_text: JSON.stringify(editing.metadata_json || {}, null, 2),
    })
  }, [editing, form])

  const mutation = useMutation({
    mutationFn: (values: BusinessContentForm) => apiRequest<BusinessContent>(`/business-content/${editing?.code}`, {
      method: "PUT",
      body: JSON.stringify({
        title_ru: values.title_ru,
        title_en: values.title_en,
        body_ru: values.body_ru || "",
        body_en: values.body_en || "",
        link_url: values.link_url || null,
        status: values.status,
        metadata_json: parseJsonObject(values.metadata_json_text),
        expected_updated_at: editing?.updated_at,
      }),
    }),
    onSuccess: () => {
      setEditing(null)
      void client.invalidateQueries({ queryKey: ["business-content"] })
      void message.success(copy.saved)
    },
    onError: (error: Error) => void message.error(error.message),
  })

  return <div className="page-stack">
    <PageHeader title={copy.title} description={copy.description} />
    <Card className="filter-card">
      <Select allowClear value={statusFilter} placeholder={copy.all} style={{ width: 210 }} options={Object.entries(statusLabels).map(([value, label]) => ({ value, label }))} onChange={setStatusFilter} />
    </Card>
    <Table<BusinessContent> rowKey="id" loading={query.isLoading} dataSource={query.data?.items} pagination={false} columns={[
      { title: copy.code, dataIndex: "code", render: (value: string) => <Typography.Text code>{value}</Typography.Text> },
      { title: copy.ru, dataIndex: "title_ru" },
      { title: copy.en, dataIndex: "title_en" },
      { title: copy.status, dataIndex: "status", render: (value: BusinessContent["status"]) => <Tag color={statusColors[value]}>{statusLabels[value]}</Tag> },
      { title: copy.version, dataIndex: "version", align: "center" },
      { title: copy.updated, dataIndex: "updated_at", render: (value: string, row) => <div className="table-primary"><strong>{dateTime(value, locale)}</strong><small>{row.updated_by_name || "—"}</small></div> },
      { title: "", align: "right", render: (_: unknown, row) => <Button icon={<EditOutlined />} onClick={() => setEditing(row)}>{copy.edit}</Button> },
    ]} />
    <Drawer width={760} open={Boolean(editing)} title={editing?.code || copy.edit} onClose={() => setEditing(null)} extra={<Button type="primary" loading={mutation.isPending} onClick={() => void form.validateFields().then((values) => mutation.mutate(values))}>{copy.save}</Button>}>
      <Tabs
        items={[
          {
            key: "content",
            label: copy.edit,
            children: <Form form={form} layout="vertical">
              <Space style={{ width: "100%" }} size={12}>
                <Form.Item name="title_ru" label={copy.ru} rules={[{ required: true }]} style={{ flex: 1 }}><Input /></Form.Item>
                <Form.Item name="title_en" label={copy.en} rules={[{ required: true }]} style={{ flex: 1 }}><Input /></Form.Item>
              </Space>
              <Form.Item name="body_ru" label={copy.bodyRu}><Input.TextArea rows={8} /></Form.Item>
              <Form.Item name="body_en" label={copy.bodyEn}><Input.TextArea rows={8} /></Form.Item>
              <Space style={{ width: "100%" }} size={12}>
                <Form.Item name="link_url" label={copy.link} style={{ flex: 2 }}><Input /></Form.Item>
                <Form.Item name="status" label={copy.status} style={{ flex: 1 }}><Select options={Object.entries(statusLabels).map(([value, label]) => ({ value, label }))} /></Form.Item>
              </Space>
              <Form.Item name="metadata_json_text" label={copy.metadata} rules={[{ validator: async (_, value) => { parseJsonObject(value || "{}") } }]}><Input.TextArea rows={5} /></Form.Item>
            </Form>,
          },
          {
            key: "history",
            label: <Space><HistoryOutlined />{copy.history}</Space>,
            children: <List
              loading={versions.isLoading}
              dataSource={versions.data || []}
              renderItem={(item) => <List.Item>
                <List.Item.Meta
                  title={<Space><Tag>v{item.version}</Tag><span>{item.actor_name || "—"}</span></Space>}
                  description={dateTime(item.created_at, locale)}
                />
              </List.Item>}
            />,
          },
        ]}
      />
    </Drawer>
  </div>
}
