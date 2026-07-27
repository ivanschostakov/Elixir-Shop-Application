import { EditOutlined, LockOutlined, SearchOutlined, UploadOutlined } from "@ant-design/icons"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Avatar, Button, Card, Drawer, Form, Image, Input, InputNumber, Select, Space, Switch, Table, Tag, Typography, Upload, message } from "antd"
import { useEffect, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { apiRequest, queryString } from "../../api/client"
import type { Category, Page, Product } from "../../api/types"
import { useAuth } from "../../auth/AuthProvider"
import { PageHeader } from "../../components/PageHeader"
import { parseVisibleColumns, TableToolbar, type TableColumnOption } from "../../components/TableToolbar"
import { useLanguage } from "../../i18n/LanguageProvider"
import { money } from "../../utils/format"

type MerchandiseForm = { description: string | null; usage: string | null; expiration: string | null; priority: number; category_ids: number[] }

export function ProductsPage() {
  const { locale } = useLanguage()
  const { hasPermission } = useAuth()
  const client = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const search = searchParams.get("q") || ""
  const archived = searchParams.get("archived") === "true"
  const lowStock = searchParams.get("low_stock") === "true"
  const page = Math.max(Number(searchParams.get("page") || 1) || 1, 1)
  const [selected, setSelected] = useState<Product | null>(null)
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [form] = Form.useForm<MerchandiseForm>()
  const pageSize = 50
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
  const query = useQuery({ queryKey: ["products", search, archived, lowStock, page], queryFn: () => apiRequest<Page<Product>>(`/products${queryString({ q: search, archived: archived || undefined, low_stock: lowStock || undefined, limit: pageSize, offset: (page - 1) * pageSize })}`) })
  const categories = useQuery({ queryKey: ["categories-all"], queryFn: () => apiRequest<Page<Category>>("/categories?limit=200&offset=0") })
  useEffect(() => { if (selected) form.setFieldsValue({ description: selected.description, usage: selected.usage, expiration: selected.expiration, priority: selected.priority, category_ids: selected.category_ids }) }, [form, selected])
  const update = useMutation({
    mutationFn: (values: MerchandiseForm) => apiRequest<Product>(`/products/${selected?.id}/merchandise`, { method: "PATCH", body: JSON.stringify({ ...values, expected_updated_at: selected?.updated_at }) }),
    onSuccess: (product) => { setSelected(null); void client.invalidateQueries({ queryKey: ["products"] }); void message.success(locale === "ru" ? "Карточка товара обновлена" : "Product updated") },
    onError: (error: Error) => void message.error(error.message),
  })
  const uploadImage = useMutation({
    mutationFn: ({ file, variantId }: { file: File; variantId?: number }) => {
      const body = new FormData()
      body.append("file", file)
      const path = variantId
        ? `/products/${selected?.id}/variants/${variantId}/image`
        : `/products/${selected?.id}/image`
      return apiRequest<Product>(path, { method: "POST", body })
    },
    onSuccess: (product) => {
      setSelected(product)
      void client.invalidateQueries({ queryKey: ["products"] })
      void message.success(locale === "ru" ? "Изображение загружено" : "Image uploaded")
    },
    onError: (error: Error) => void message.error(error.message),
  })
  const copy = locale === "ru"
    ? { title: "Товары", description: "Данные МойСклад и локальное оформление витрины", search: "Название или SKU", archived: "Показать архив", lowStock: "Только низкие остатки", product: "Товар", source: "Источник", stock: "Остаток", price: "Цена", priority: "Приоритет", state: "Статус", edit: "Оформление", drawer: "Оформление товара", locked: "Название, SKU, цены и остатки синхронизируются из МойСклад", descriptionField: "Описание", usage: "Применение", expiration: "Срок годности", categories: "Категории", save: "Сохранить", active: "Активен", out: "Нет в наличии", archivedState: "В архиве", mainImage: "Основное изображение", variantImages: "Изображения вариантов", upload: "Загрузить", imageHint: "JPEG, PNG или WEBP до 10 МБ. Изображение будет сохранено в PNG." }
    : { title: "Products", description: "MoySklad data and local storefront content", search: "Name or SKU", archived: "Show archived", lowStock: "Low stock only", product: "Product", source: "Source", stock: "Stock", price: "Price", priority: "Priority", state: "Status", edit: "Merchandising", drawer: "Product merchandising", locked: "Name, SKU, prices and stock are synchronized from MoySklad", descriptionField: "Description", usage: "Usage", expiration: "Expiration", categories: "Categories", save: "Save", active: "Active", out: "Out of stock", archivedState: "Archived", mainImage: "Main image", variantImages: "Variant images", upload: "Upload", imageHint: "JPEG, PNG or WEBP up to 10 MB. The image will be stored as PNG." }
  const tableColumns = [
    { title: copy.product, key: "product", render: (_: unknown, row: Product) => <Space><Avatar shape="square" size={48} src={row.image_url} icon={<ProductFallback />} /><div className="table-primary"><strong>{row.name}</strong><small>{row.sku}</small></div></Space> },
    { title: copy.source, key: "source", render: () => <Tag bordered={false}>МойСклад</Tag> },
    { title: copy.stock, key: "stock", render: (_: unknown, row: Product) => row.variants.reduce((sum, variant) => sum + variant.stock, 0) },
    { title: copy.price, key: "price", render: (_: unknown, row: Product) => row.variants.length ? `${money(Math.min(...row.variants.map((variant) => Number(variant.price))), "RUB", locale)} — ${money(Math.max(...row.variants.map((variant) => Number(variant.price))), "RUB", locale)}` : "—" },
    { title: copy.priority, dataIndex: "priority", key: "priority", align: "center" as const },
    { title: copy.state, key: "state", render: (_: unknown, row: Product) => <Space><Tag color={row.archived ? "default" : row.in_stock ? "green" : "orange"}>{row.archived ? copy.archivedState : row.in_stock ? copy.active : copy.out}</Tag></Space> },
    { title: "", key: "edit", align: "right" as const, render: (_: unknown, row: Product) => hasPermission("catalog.merchandise") ? <Button icon={<EditOutlined />} onClick={() => setSelected(row)}>{copy.edit}</Button> : null },
  ]
  const columnOptions: TableColumnOption[] = [
    { key: "product", label: copy.product, exportKeys: ["sku", "name"] },
    { key: "source", label: copy.source },
    { key: "stock", label: copy.stock, exportKeys: ["stock"] },
    { key: "price", label: copy.price, exportKeys: ["price"] },
    { key: "priority", label: copy.priority, exportKeys: ["priority"] },
    { key: "state", label: copy.state, exportKeys: ["in_stock", "archived"] },
    { key: "edit", label: copy.edit },
  ]
  const visibleColumns = parseVisibleColumns(searchParams.get("columns"), columnOptions.map((column) => column.key))
  const viewState = Object.fromEntries(Array.from(searchParams.entries()).filter(([key]) => key !== "page"))

  return (
    <div className="page-stack">
      <PageHeader title={copy.title} description={copy.description} />
      <Card className="filter-card"><Space wrap><Input allowClear prefix={<SearchOutlined />} placeholder={copy.search} value={search} onChange={(event) => updateFilters({ q: event.target.value, page: 1 })} /><Space><Switch checked={archived} onChange={(value) => updateFilters({ archived: value ? "true" : undefined, page: 1 })} />{copy.archived}</Space><Space><Switch checked={lowStock} onChange={(value) => updateFilters({ low_stock: value ? "true" : undefined, page: 1 })} />{copy.lowStock}</Space></Space></Card>
      <TableToolbar
        resource="products"
        columns={columnOptions}
        visibleColumns={visibleColumns}
        onVisibleColumnsChange={(keys) => updateFilters({ columns: keys.length === columnOptions.length ? undefined : keys.join(","), page: 1 })}
        viewState={viewState}
        onApplyViewState={(state) => { setSelectedRowKeys([]); setSearchParams(state) }}
        exportFilters={{ q: search, archived: archived || undefined, low_stock: lowStock || undefined }}
        selectedIds={selectedRowKeys.map(Number)}
        onClearSelection={() => setSelectedRowKeys([])}
      />
      <Table<Product>
        rowKey="id"
        loading={query.isLoading}
        dataSource={query.data?.items}
        rowSelection={{ selectedRowKeys, preserveSelectedRowKeys: true, onChange: setSelectedRowKeys }}
        pagination={{ current: page, pageSize, total: query.data?.total, showSizeChanger: false, onChange: (nextPage) => updateFilters({ page: nextPage }) }}
        expandable={{ expandedRowRender: (product) => <Table rowKey="id" pagination={false} size="small" dataSource={product.variants} columns={[{ title: "SKU", dataIndex: "sku" }, { title: locale === "ru" ? "Вариант" : "Variant", dataIndex: "name" }, { title: copy.stock, dataIndex: "stock" }, { title: copy.price, dataIndex: "price", render: (value: string) => money(value, "RUB", locale) }, { title: copy.state, dataIndex: "archived", render: (value: boolean) => <Tag color={value ? "default" : "green"}>{value ? copy.archivedState : copy.active}</Tag> }]} /> }}
        columns={tableColumns.filter((column) => visibleColumns.includes(String(column.key)))}
      />
      <Drawer width={620} open={Boolean(selected)} onClose={() => setSelected(null)} title={copy.drawer} extra={<Button type="primary" loading={update.isPending} onClick={() => void form.validateFields().then((values) => update.mutate(values))}>{copy.save}</Button>}>
        {selected ? <>
          <div className="source-lock"><LockOutlined /><div><strong>{selected.name}</strong><span>{copy.locked}</span></div></div>
          <Typography.Title level={5}>{copy.mainImage}</Typography.Title>
          <Space align="start" style={{ marginBottom: 8 }}>
            <Image width={112} height={112} style={{ objectFit: "contain", borderRadius: 10 }} src={selected.image_url} />
            <Upload
              accept="image/jpeg,image/png,image/webp"
              maxCount={1}
              showUploadList={false}
              customRequest={({ file, onSuccess, onError }) => {
                uploadImage.mutate(
                  { file: file as File },
                  { onSuccess: () => onSuccess?.({}), onError: (error) => onError?.(error as Error) },
                )
              }}
            >
              <Button icon={<UploadOutlined />} loading={uploadImage.isPending}>{copy.upload}</Button>
            </Upload>
          </Space>
          <Typography.Paragraph type="secondary">{copy.imageHint}</Typography.Paragraph>
          <Typography.Title level={5}>{copy.variantImages}</Typography.Title>
          <Space direction="vertical" style={{ width: "100%", marginBottom: 20 }}>
            {selected.variants.map((variant) => (
              <div key={variant.id} className="product-variant-image-row">
                <Image width={56} height={56} style={{ objectFit: "contain", borderRadius: 8 }} src={variant.image_url} />
                <div className="table-primary"><strong>{variant.name}</strong><small>{variant.sku || "—"}</small></div>
                <Upload
                  accept="image/jpeg,image/png,image/webp"
                  maxCount={1}
                  showUploadList={false}
                  customRequest={({ file, onSuccess, onError }) => {
                    uploadImage.mutate(
                      { file: file as File, variantId: variant.id },
                      { onSuccess: () => onSuccess?.({}), onError: (error) => onError?.(error as Error) },
                    )
                  }}
                >
                  <Button size="small" icon={<UploadOutlined />}>{copy.upload}</Button>
                </Upload>
              </div>
            ))}
          </Space>
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
