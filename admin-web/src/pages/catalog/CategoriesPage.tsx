import { EditOutlined, PlusOutlined, SearchOutlined } from "@ant-design/icons"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Button, Card, Form, Input, Modal, Space, Switch, Table, Tag, message } from "antd"
import { useEffect, useState } from "react"
import { apiRequest, queryString } from "../../api/client"
import type { Category, Page } from "../../api/types"
import { useAuth } from "../../auth/AuthProvider"
import { PageHeader } from "../../components/PageHeader"
import { useLanguage } from "../../i18n/LanguageProvider"
import { dateTime } from "../../utils/format"

type CategoryForm = { name: string; description: string | null; archived: boolean }

export function CategoriesPage() {
  const { locale } = useLanguage()
  const { hasPermission } = useAuth()
  const client = useQueryClient()
  const [search, setSearch] = useState("")
  const [editing, setEditing] = useState<Category | "new" | null>(null)
  const [form] = Form.useForm<CategoryForm>()
  const query = useQuery({ queryKey: ["categories", search], queryFn: () => apiRequest<Page<Category>>(`/categories${queryString({ q: search, limit: 200 })}`) })
  useEffect(() => {
    if (editing === "new") form.setFieldsValue({ name: "", description: null, archived: false })
    else if (editing) form.setFieldsValue({ name: editing.name, description: editing.description, archived: editing.archived })
  }, [editing, form])
  const mutation = useMutation({
    mutationFn: (values: CategoryForm) => apiRequest<Category>(editing === "new" ? "/categories" : `/categories/${editing?.id}`, { method: editing === "new" ? "POST" : "PUT", body: JSON.stringify(values) }),
    onSuccess: () => { setEditing(null); void client.invalidateQueries({ queryKey: ["categories"] }); void client.invalidateQueries({ queryKey: ["categories-all"] }); void message.success(locale === "ru" ? "Категория сохранена" : "Category saved") },
    onError: (error: Error) => void message.error(error.message),
  })
  const copy = locale === "ru" ? { title: "Категории", description: "Структура каталога и навигация витрины", add: "Добавить категорию", search: "Найти категорию", name: "Название", descriptionField: "Описание", state: "Статус", updated: "Обновлено", active: "Активна", archived: "В архиве", edit: "Редактировать", save: "Сохранить" } : { title: "Categories", description: "Catalog structure and storefront navigation", add: "Add category", search: "Find category", name: "Name", descriptionField: "Description", state: "Status", updated: "Updated", active: "Active", archived: "Archived", edit: "Edit", save: "Save" }
  return <div className="page-stack">
    <PageHeader title={copy.title} description={copy.description} actions={hasPermission("categories.manage") ? <Button type="primary" icon={<PlusOutlined />} onClick={() => setEditing("new")}>{copy.add}</Button> : null} />
    <Card className="filter-card"><Input allowClear prefix={<SearchOutlined />} placeholder={copy.search} value={search} onChange={(event) => setSearch(event.target.value)} /></Card>
    <Table<Category> rowKey="id" loading={query.isLoading} dataSource={query.data?.items} pagination={false} columns={[
      { title: copy.name, dataIndex: "name", render: (value: string) => <strong>{value}</strong> },
      { title: copy.descriptionField, dataIndex: "description", ellipsis: true },
      { title: copy.state, dataIndex: "archived", render: (value: boolean) => <Tag color={value ? "default" : "green"}>{value ? copy.archived : copy.active}</Tag> },
      { title: copy.updated, dataIndex: "updated_at", render: (value: string) => dateTime(value, locale) },
      { title: "", align: "right", render: (_: unknown, row) => hasPermission("categories.manage") ? <Button icon={<EditOutlined />} onClick={() => setEditing(row)}>{copy.edit}</Button> : null },
    ]} />
    <Modal open={Boolean(editing)} title={editing === "new" ? copy.add : copy.edit} okText={copy.save} confirmLoading={mutation.isPending} onCancel={() => setEditing(null)} onOk={() => void form.validateFields().then((values) => mutation.mutate(values))}>
      <Form form={form} layout="vertical"><Form.Item name="name" label={copy.name} rules={[{ required: true, max: 200 }]}><Input /></Form.Item><Form.Item name="description" label={copy.descriptionField}><Input.TextArea rows={4} /></Form.Item><Form.Item name="archived" label={copy.archived} valuePropName="checked"><Switch /></Form.Item></Form>
    </Modal>
  </div>
}
