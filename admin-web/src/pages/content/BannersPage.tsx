import { EditOutlined, PlusOutlined } from "@ant-design/icons"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Button, Card, Form, Input, InputNumber, Modal, Space, Switch, Table, Tag, message } from "antd"
import { useEffect, useState } from "react"
import { apiRequest } from "../../api/client"
import type { Banner, Page } from "../../api/types"
import { PageHeader } from "../../components/PageHeader"
import { useLanguage } from "../../i18n/LanguageProvider"
import { dateTime } from "../../utils/format"

type BannerForm = { image_path: string; inner_link: string | null; outer_link: string | null; priority: number; archived: boolean }

export function BannersPage() {
  const { locale } = useLanguage()
  const client = useQueryClient()
  const [editing, setEditing] = useState<Banner | "new" | null>(null)
  const [form] = Form.useForm<BannerForm>()
  const query = useQuery({ queryKey: ["banners"], queryFn: () => apiRequest<Page<Banner>>("/banners?limit=100") })
  useEffect(() => {
    if (editing === "new") form.setFieldsValue({ image_path: "", inner_link: null, outer_link: null, priority: 0, archived: false })
    else if (editing) form.setFieldsValue(editing)
  }, [editing, form])
  const mutation = useMutation({
    mutationFn: (values: BannerForm) => apiRequest<Banner>(editing === "new" ? "/banners" : `/banners/${editing?.id}`, { method: editing === "new" ? "POST" : "PUT", body: JSON.stringify(editing === "new" ? values : { ...values, expected_updated_at: editing?.updated_at }) }),
    onSuccess: () => { setEditing(null); void client.invalidateQueries({ queryKey: ["banners"] }); void message.success(locale === "ru" ? "Баннер сохранён" : "Banner saved") },
    onError: (error: Error) => void message.error(error.message),
  })
  const copy = locale === "ru" ? { title: "Баннеры", description: "Промо-блоки мобильной витрины", add: "Добавить", image: "Путь к изображению", inner: "Ссылка внутри приложения", outer: "Внешняя ссылка", priority: "Приоритет", state: "Статус", updated: "Обновлено", active: "Активен", archived: "В архиве", edit: "Редактировать", save: "Сохранить" } : { title: "Banners", description: "Promotional blocks in the mobile storefront", add: "Add", image: "Image path", inner: "In-app link", outer: "External link", priority: "Priority", state: "Status", updated: "Updated", active: "Active", archived: "Archived", edit: "Edit", save: "Save" }
  return <div className="page-stack">
    <PageHeader title={copy.title} description={copy.description} actions={<Button type="primary" icon={<PlusOutlined />} onClick={() => setEditing("new")}>{copy.add}</Button>} />
    <Table<Banner> rowKey="id" loading={query.isLoading} dataSource={query.data?.items} pagination={false} columns={[
      { title: copy.image, dataIndex: "image_path", ellipsis: true },
      { title: copy.inner, dataIndex: "inner_link", render: (value: string | null) => value || "—" },
      { title: copy.outer, dataIndex: "outer_link", render: (value: string | null) => value || "—" },
      { title: copy.priority, dataIndex: "priority", align: "center" },
      { title: copy.state, dataIndex: "archived", render: (value: boolean) => <Tag color={value ? "default" : "green"}>{value ? copy.archived : copy.active}</Tag> },
      { title: copy.updated, dataIndex: "updated_at", render: (value: string) => dateTime(value, locale) },
      { title: "", align: "right", render: (_: unknown, row) => <Button icon={<EditOutlined />} onClick={() => setEditing(row)}>{copy.edit}</Button> },
    ]} />
    <Modal open={Boolean(editing)} title={editing === "new" ? copy.add : copy.edit} okText={copy.save} confirmLoading={mutation.isPending} onCancel={() => setEditing(null)} onOk={() => void form.validateFields().then((values) => mutation.mutate(values))}>
      <Form form={form} layout="vertical"><Form.Item name="image_path" label={copy.image} rules={[{ required: true }]}><Input /></Form.Item><Form.Item name="inner_link" label={copy.inner}><Input /></Form.Item><Form.Item name="outer_link" label={copy.outer}><Input /></Form.Item><Form.Item name="priority" label={copy.priority}><InputNumber min={0} style={{ width: "100%" }} /></Form.Item><Form.Item name="archived" label={copy.archived} valuePropName="checked"><Switch /></Form.Item></Form>
    </Modal>
  </div>
}
