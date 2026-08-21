import { EditOutlined, PlusOutlined, SearchOutlined } from "@ant-design/icons"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Button, Card, Form, Input, InputNumber, Modal, Space, Switch, Table, Tag, message } from "antd"
import { useEffect, useState } from "react"
import { apiRequest, queryString } from "../../api/client"
import type { Category, Page } from "../../api/types"
import { useAuth } from "../../auth/AuthProvider"
import { PageHeader } from "../../components/PageHeader"
import { useLanguage } from "../../i18n/LanguageProvider"
import { dateTime } from "../../utils/format"

type CategoryForm = {
  name: string
  description: string | null
  archived: boolean
  is_visible_in_app: boolean
  app_display_order: number
  discount_percent: number
}

function categoryPayload(category: Category, overrides: Partial<CategoryForm> = {}): CategoryForm {
  return {
    name: category.name,
    description: category.description,
    archived: category.archived,
    is_visible_in_app: category.is_visible_in_app,
    app_display_order: category.app_display_order,
    discount_percent: Number(category.discount_percent),
    ...overrides,
  }
}

export function CategoriesPage() {
  const { locale } = useLanguage()
  const { hasPermission } = useAuth()
  const client = useQueryClient()
  const [search, setSearch] = useState("")
  const [editing, setEditing] = useState<Category | "new" | null>(null)
  const [form] = Form.useForm<CategoryForm>()
  const query = useQuery({ queryKey: ["categories", search], queryFn: () => apiRequest<Page<Category>>(`/categories${queryString({ q: search, limit: 200 })}`) })
  useEffect(() => {
    if (editing === "new") {
      const nextOrder = Math.max(0, ...(query.data?.items.map((category) => category.app_display_order) || [])) + 10
      form.setFieldsValue({ name: "", description: null, archived: false, is_visible_in_app: true, app_display_order: nextOrder, discount_percent: 0 })
    } else if (editing) {
      form.setFieldsValue(categoryPayload(editing))
    }
  }, [editing, form, query.data?.items])
  const mutation = useMutation({
    mutationFn: (values: CategoryForm) => apiRequest<Category>(editing === "new" ? "/categories" : `/categories/${editing?.id}`, { method: editing === "new" ? "POST" : "PUT", body: JSON.stringify(values) }),
    onSuccess: () => { setEditing(null); void client.invalidateQueries({ queryKey: ["categories"] }); void client.invalidateQueries({ queryKey: ["categories-all"] }); void message.success(locale === "ru" ? "Категория сохранена" : "Category saved") },
    onError: (error: Error) => void message.error(error.message),
  })
  const visibilityMutation = useMutation({
    mutationFn: ({ category, visible }: { category: Category; visible: boolean }) => apiRequest<Category>(`/categories/${category.id}`, { method: "PUT", body: JSON.stringify(categoryPayload(category, { is_visible_in_app: visible })) }),
    onSuccess: () => { void client.invalidateQueries({ queryKey: ["categories"] }); void client.invalidateQueries({ queryKey: ["categories-all"] }) },
    onError: (error: Error) => void message.error(error.message),
  })
  const copy = locale === "ru"
    ? { title: "Категории", description: "Структура каталога, порядок показа в приложении и скидки", add: "Добавить категорию", search: "Найти категорию", name: "Название", descriptionField: "Описание", discount: "Скидка на категорию, %", discountHint: "Применяется ко всем товарам категории, если она выгоднее скидки самого товара.", appVisibility: "Показ в приложении", shown: "Показывается", hidden: "Скрыта", appOrder: "Порядок", appOrderHint: "Категории с меньшим номером показываются раньше. Для удобства используйте шаг 10.", state: "Статус", updated: "Обновлено", active: "Активна", archived: "В архиве", edit: "Редактировать", save: "Сохранить" }
    : { title: "Categories", description: "Catalog structure, app display order, and discounts", add: "Add category", search: "Find category", name: "Name", descriptionField: "Description", discount: "Category discount, %", discountHint: "Applies to all category products when it is better than the product discount.", appVisibility: "Shown in app", shown: "Shown", hidden: "Hidden", appOrder: "Order", appOrderHint: "Categories with a lower number appear first. Use increments of 10 for easier reordering.", state: "Status", updated: "Updated", active: "Active", archived: "Archived", edit: "Edit", save: "Save" }
  return <div className="page-stack">
    <PageHeader title={copy.title} description={copy.description} actions={hasPermission("categories.manage") ? <Button type="primary" icon={<PlusOutlined />} onClick={() => setEditing("new")}>{copy.add}</Button> : null} />
    <Card className="filter-card"><Input allowClear prefix={<SearchOutlined />} placeholder={copy.search} value={search} onChange={(event) => setSearch(event.target.value)} /></Card>
    <Table<Category> rowKey="id" loading={query.isLoading} dataSource={query.data?.items} pagination={false} columns={[
      { title: copy.name, dataIndex: "name", render: (value: string) => <strong>{value}</strong> },
      { title: copy.descriptionField, dataIndex: "description", ellipsis: true },
      { title: copy.appOrder, dataIndex: "app_display_order", width: 100 },
      { title: copy.appVisibility, dataIndex: "is_visible_in_app", width: 170, render: (value: boolean, row) => hasPermission("categories.manage") ? <Space><Switch checked={value} loading={visibilityMutation.isPending && visibilityMutation.variables?.category.id === row.id} onChange={(visible) => visibilityMutation.mutate({ category: row, visible })} /><span>{value ? copy.shown : copy.hidden}</span></Space> : <Tag color={value ? "green" : "default"}>{value ? copy.shown : copy.hidden}</Tag> },
      { title: copy.discount, dataIndex: "discount_percent", render: (value: string) => Number(value) > 0 ? <Tag color="volcano">−{Number(value)}%</Tag> : "—" },
      { title: copy.state, dataIndex: "archived", render: (value: boolean) => <Tag color={value ? "default" : "green"}>{value ? copy.archived : copy.active}</Tag> },
      { title: copy.updated, dataIndex: "updated_at", render: (value: string) => dateTime(value, locale) },
      { title: "", align: "right", render: (_: unknown, row) => hasPermission("categories.manage") ? <Button icon={<EditOutlined />} onClick={() => setEditing(row)}>{copy.edit}</Button> : null },
    ]} />
    <Modal open={Boolean(editing)} title={editing === "new" ? copy.add : copy.edit} okText={copy.save} confirmLoading={mutation.isPending} onCancel={() => setEditing(null)} onOk={() => void form.validateFields().then((values) => mutation.mutate(values))}>
      <Form form={form} layout="vertical"><Form.Item name="name" label={copy.name} rules={[{ required: true, max: 200 }]}><Input /></Form.Item><Form.Item name="description" label={copy.descriptionField}><Input.TextArea rows={4} /></Form.Item><Form.Item name="app_display_order" label={copy.appOrder} extra={copy.appOrderHint} rules={[{ required: true }]}><InputNumber min={0} precision={0} step={10} style={{ width: "100%" }} /></Form.Item><Form.Item name="is_visible_in_app" label={copy.appVisibility} valuePropName="checked"><Switch checkedChildren={copy.shown} unCheckedChildren={copy.hidden} /></Form.Item><Form.Item name="discount_percent" label={copy.discount} extra={copy.discountHint} rules={[{ required: true }]}><InputNumber min={0} max={100} precision={2} addonAfter="%" style={{ width: "100%" }} /></Form.Item><Form.Item name="archived" label={copy.archived} valuePropName="checked"><Switch /></Form.Item></Form>
    </Modal>
  </div>
}
