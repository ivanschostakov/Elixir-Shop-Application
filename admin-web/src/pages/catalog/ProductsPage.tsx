import { EditOutlined, LockOutlined, SearchOutlined } from "@ant-design/icons"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Avatar, Button, Card, Drawer, Form, Input, InputNumber, Select, Space, Switch, Table, Tag, Typography, message } from "antd"
import { useEffect, useState } from "react"
import { apiRequest, queryString } from "../../api/client"
import type { Category, Page, Product } from "../../api/types"
import { useAuth } from "../../auth/AuthProvider"
import { PageHeader } from "../../components/PageHeader"
import { useLanguage } from "../../i18n/LanguageProvider"
import { money } from "../../utils/format"

type MerchandiseForm = { description: string | null; usage: string | null; expiration: string | null; priority: number; category_ids: number[] }

export function ProductsPage() {
  const { locale } = useLanguage()
  const { hasPermission } = useAuth()
  const client = useQueryClient()
  const [search, setSearch] = useState("")
  const [archived, setArchived] = useState(false)
  const [selected, setSelected] = useState<Product | null>(null)
  const [page, setPage] = useState(1)
  const [form] = Form.useForm<MerchandiseForm>()
  const pageSize = 50
  const query = useQuery({ queryKey: ["products", search, archived, page], queryFn: () => apiRequest<Page<Product>>(`/products${queryString({ q: search, archived: archived || undefined, limit: pageSize, offset: (page - 1) * pageSize })}`) })
  const categories = useQuery({ queryKey: ["categories-all"], queryFn: () => apiRequest<Page<Category>>("/categories?limit=200&offset=0") })
  useEffect(() => { if (selected) form.setFieldsValue({ description: selected.description, usage: selected.usage, expiration: selected.expiration, priority: selected.priority, category_ids: selected.category_ids }) }, [form, selected])
  const update = useMutation({
    mutationFn: (values: MerchandiseForm) => apiRequest<Product>(`/products/${selected?.id}/merchandise`, { method: "PATCH", body: JSON.stringify({ ...values, expected_updated_at: selected?.updated_at }) }),
    onSuccess: (product) => { setSelected(null); void client.invalidateQueries({ queryKey: ["products"] }); void message.success(locale === "ru" ? "Карточка товара обновлена" : "Product updated") },
    onError: (error: Error) => void message.error(error.message),
  })
  const copy = locale === "ru"
    ? { title: "Товары", description: "Данные МойСклад и локальное оформление витрины", search: "Название или SKU", archived: "Показать архив", product: "Товар", source: "Источник", stock: "Остаток", price: "Цена", priority: "Приоритет", state: "Статус", edit: "Оформление", drawer: "Оформление товара", locked: "Название, SKU, цены и остатки синхронизируются из МойСклад", descriptionField: "Описание", usage: "Применение", expiration: "Срок годности", categories: "Категории", save: "Сохранить", active: "Активен", out: "Нет в наличии" }
    : { title: "Products", description: "MoySklad data and local storefront content", search: "Name or SKU", archived: "Show archived", product: "Product", source: "Source", stock: "Stock", price: "Price", priority: "Priority", state: "Status", edit: "Merchandising", drawer: "Product merchandising", locked: "Name, SKU, prices and stock are synchronized from MoySklad", descriptionField: "Description", usage: "Usage", expiration: "Expiration", categories: "Categories", save: "Save", active: "Active", out: "Out of stock" }

  return (
    <div className="page-stack">
      <PageHeader title={copy.title} description={copy.description} />
      <Card className="filter-card"><Space wrap><Input allowClear prefix={<SearchOutlined />} placeholder={copy.search} value={search} onChange={(event) => { setSearch(event.target.value); setPage(1) }} /><Space><Switch checked={archived} onChange={(value) => { setArchived(value); setPage(1) }} />{copy.archived}</Space></Space></Card>
      <Table<Product>
        rowKey="id"
        loading={query.isLoading}
        dataSource={query.data?.items}
        pagination={{ current: page, pageSize, total: query.data?.total, showSizeChanger: false, onChange: setPage }}
        expandable={{ expandedRowRender: (product) => <Table rowKey="id" pagination={false} size="small" dataSource={product.variants} columns={[{ title: "SKU", dataIndex: "sku" }, { title: locale === "ru" ? "Вариант" : "Variant", dataIndex: "name" }, { title: copy.stock, dataIndex: "stock" }, { title: copy.price, dataIndex: "price", render: (value: string) => money(value, "RUB", locale) }, { title: copy.state, dataIndex: "archived", render: (value: boolean) => <Tag color={value ? "default" : "green"}>{value ? "Archived" : copy.active}</Tag> }]} /> }}
        columns={[
          { title: copy.product, key: "product", render: (_: unknown, row) => <Space><Avatar shape="square" size={48} src={row.image_url} icon={<ProductFallback />} /><div className="table-primary"><strong>{row.name}</strong><small>{row.sku}</small></div></Space> },
          { title: copy.source, render: () => <Tag bordered={false}>МойСклад</Tag> },
          { title: copy.stock, key: "stock", render: (_: unknown, row) => row.variants.reduce((sum, variant) => sum + variant.stock, 0) },
          { title: copy.price, key: "price", render: (_: unknown, row) => row.variants.length ? `${money(Math.min(...row.variants.map((variant) => Number(variant.price))), "RUB", locale)} — ${money(Math.max(...row.variants.map((variant) => Number(variant.price))), "RUB", locale)}` : "—" },
          { title: copy.priority, dataIndex: "priority", align: "center" },
          { title: copy.state, key: "state", render: (_: unknown, row) => <Space><Tag color={row.archived ? "default" : row.in_stock ? "green" : "orange"}>{row.archived ? "Archived" : row.in_stock ? copy.active : copy.out}</Tag></Space> },
          { title: "", key: "edit", align: "right", render: (_: unknown, row) => hasPermission("catalog.merchandise") ? <Button icon={<EditOutlined />} onClick={() => setSelected(row)}>{copy.edit}</Button> : null },
        ]}
      />
      <Drawer width={620} open={Boolean(selected)} onClose={() => setSelected(null)} title={copy.drawer} extra={<Button type="primary" loading={update.isPending} onClick={() => void form.validateFields().then((values) => update.mutate(values))}>{copy.save}</Button>}>
        {selected ? <>
          <div className="source-lock"><LockOutlined /><div><strong>{selected.name}</strong><span>{copy.locked}</span></div></div>
          <Form form={form} layout="vertical" requiredMark={false}>
            <Form.Item name="description" label={copy.descriptionField}><Input.TextArea rows={7} /></Form.Item>
            <Form.Item name="usage" label={copy.usage}><Input.TextArea rows={5} /></Form.Item>
            <Form.Item name="expiration" label={copy.expiration}><Input.TextArea rows={3} /></Form.Item>
            <Form.Item name="priority" label={copy.priority} rules={[{ required: true }]}><InputNumber min={0} style={{ width: "100%" }} /></Form.Item>
            <Form.Item name="category_ids" label={copy.categories}><Select mode="multiple" optionFilterProp="label" options={(categories.data?.items || []).map((category) => ({ value: category.id, label: category.name }))} /></Form.Item>
          </Form>
        </> : null}
      </Drawer>
    </div>
  )
}

function ProductFallback() {
  return <Typography.Text>P</Typography.Text>
}
