import { ArrowLeftOutlined, LockOutlined, MessageOutlined, UnlockOutlined } from "@ant-design/icons"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Avatar, Button, Card, Col, Descriptions, Form, Input, List, Modal, Row, Space, Statistic, Tag, Typography, message } from "antd"
import { useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { apiRequest } from "../../api/client"
import type { CustomerDetail } from "../../api/types"
import { useAuth } from "../../auth/AuthProvider"
import { PageHeader } from "../../components/PageHeader"
import { QueryState } from "../../components/QueryState"
import { useLanguage } from "../../i18n/LanguageProvider"
import { dateTime, money } from "../../utils/format"

export function CustomerDetailPage() {
  const { customerId } = useParams()
  const navigate = useNavigate()
  const { locale } = useLanguage()
  const { hasPermission } = useAuth()
  const client = useQueryClient()
  const [noteOpen, setNoteOpen] = useState(false)
  const [form] = Form.useForm<{ body: string }>()
  const query = useQuery({ queryKey: ["customer", customerId], queryFn: () => apiRequest<CustomerDetail>(`/customers/${customerId}`), enabled: Boolean(customerId) })
  const statusMutation = useMutation({
    mutationFn: (customer: CustomerDetail) => apiRequest<CustomerDetail>(`/customers/${customer.id}/status`, { method: "PATCH", body: JSON.stringify({ is_active: !customer.is_active, expected_updated_at: customer.updated_at }) }),
    onSuccess: (data) => { client.setQueryData(["customer", customerId], data); void client.invalidateQueries({ queryKey: ["customers"] }); void message.success(locale === "ru" ? "Статус клиента обновлён" : "Customer status updated") },
    onError: (error: Error) => void message.error(error.message),
  })
  const noteMutation = useMutation({
    mutationFn: (body: string) => apiRequest(`/customers/${customerId}/notes`, { method: "POST", body: JSON.stringify({ body }) }),
    onSuccess: () => { form.resetFields(); setNoteOpen(false); void query.refetch(); void message.success(locale === "ru" ? "Заметка добавлена" : "Note added") },
    onError: (error: Error) => void message.error(error.message),
  })
  const customer = query.data
  const copy = locale === "ru"
    ? { description: "Карточка клиента 360°", back: "К списку", block: "Заблокировать", unblock: "Разблокировать", note: "Добавить заметку", revenue: "Выручка", orders: "Заказы", basket: "Корзина", views: "Просмотры", profile: "Профиль", activity: "Активность и интересы", referrals: "Реферальная программа", notes: "Внутренние заметки", noNotes: "Заметок пока нет", noteTitle: "Новая заметка", notePlaceholder: "Контекст для коллег…", save: "Сохранить" }
    : { description: "360° customer profile", back: "Back", block: "Block", unblock: "Unblock", note: "Add note", revenue: "Revenue", orders: "Orders", basket: "Basket", views: "Views", profile: "Profile", activity: "Activity & interests", referrals: "Referral program", notes: "Internal notes", noNotes: "No notes yet", noteTitle: "New note", notePlaceholder: "Context for your team…", save: "Save" }

  return (
    <div className="page-stack">
      <PageHeader
        title={customer ? `${customer.name} ${customer.surname}` : locale === "ru" ? "Клиент" : "Customer"}
        description={copy.description}
        actions={<Space><Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/customers")}>{copy.back}</Button>{customer && hasPermission("customers.manage") ? <Button danger={customer.is_active} icon={customer.is_active ? <LockOutlined /> : <UnlockOutlined />} loading={statusMutation.isPending} onClick={() => statusMutation.mutate(customer)}>{customer.is_active ? copy.block : copy.unblock}</Button> : null}</Space>}
      />
      <QueryState loading={query.isLoading} error={query.isError} onRetry={() => void query.refetch()} />
      {customer ? (
        <>
          <Row gutter={[16, 16]}>
            <Col xs={12} lg={6}><Card><Statistic title={copy.revenue} value={money(customer.paid_total, "RUB", locale)} /></Card></Col>
            <Col xs={12} lg={6}><Card><Statistic title={copy.orders} value={customer.orders_count} /></Card></Col>
            <Col xs={12} lg={6}><Card><Statistic title={copy.basket} value={money(customer.basket_total, "RUB", locale)} suffix={`· ${customer.basket_items}`} /></Card></Col>
            <Col xs={12} lg={6}><Card><Statistic title={copy.views} value={customer.total_product_views} /></Card></Col>
          </Row>
          <Row gutter={[16, 16]}>
            <Col xs={24} xl={14}>
              <Card title={copy.profile}>
                <Space size={16} align="start" className="customer-identity"><Avatar size={64}>{`${customer.name[0] || ""}${customer.surname[0] || ""}`}</Avatar><div><Typography.Title level={4}>{customer.name} {customer.surname}</Typography.Title><Space><Tag color={customer.is_active ? "green" : "red"}>{customer.is_active ? "Active" : "Blocked"}</Tag>{customer.is_verified ? <Tag color="blue">Verified</Tag> : null}</Space></div></Space>
                <Descriptions column={{ xs: 1, md: 2 }}>
                  <Descriptions.Item label="Email">{customer.email || "—"}</Descriptions.Item>
                  <Descriptions.Item label="Phone">{customer.phone_number || "—"}</Descriptions.Item>
                  <Descriptions.Item label="Telegram">{customer.telegram_username ? `@${customer.telegram_username}` : "—"}</Descriptions.Item>
                  <Descriptions.Item label="amoCRM">{customer.contact_id || "—"}</Descriptions.Item>
                  <Descriptions.Item label="МойСклад">{customer.moysklad_counterparty_id || "—"}</Descriptions.Item>
                  <Descriptions.Item label={locale === "ru" ? "Последняя активность" : "Last active"}>{dateTime(customer.last_active_at, locale)}</Descriptions.Item>
                </Descriptions>
              </Card>
              <Card title={copy.activity}>
                <Row gutter={[16, 16]}><Col span={8}><Statistic title={locale === "ru" ? "Избранное" : "Favorites"} value={customer.favourites_count} /></Col><Col span={8}><Statistic title={locale === "ru" ? "В корзинах" : "Cart quantity"} value={customer.total_cart_quantity} /></Col><Col span={8}><Statistic title="Push tokens" value={customer.push_tokens_count} /></Col></Row>
              </Card>
              <Card title={copy.referrals}><Descriptions><Descriptions.Item label="Promo">{customer.promo_code || "—"}</Descriptions.Item><Descriptions.Item label={locale === "ru" ? "База скидки" : "Discount base"}>{money(customer.referral_discount_base_total, "RUB", locale)}</Descriptions.Item><Descriptions.Item label={locale === "ru" ? "Текущая скидка" : "Current discount"}>{customer.referral_discount_percent}%</Descriptions.Item></Descriptions></Card>
            </Col>
            <Col xs={24} xl={10}>
              <Card title={copy.notes} extra={hasPermission("customers.notes") ? <Button size="small" icon={<MessageOutlined />} onClick={() => setNoteOpen(true)}>{copy.note}</Button> : null}>
                <List locale={{ emptyText: copy.noNotes }} dataSource={customer.notes} renderItem={(note) => <List.Item><List.Item.Meta title={<Space><strong>{note.author_name}</strong><Typography.Text type="secondary">{dateTime(note.created_at, locale)}</Typography.Text></Space>} description={<Typography.Paragraph>{note.body}</Typography.Paragraph>} /></List.Item>} />
              </Card>
            </Col>
          </Row>
        </>
      ) : null}
      <Modal open={noteOpen} title={copy.noteTitle} okText={copy.save} confirmLoading={noteMutation.isPending} onCancel={() => setNoteOpen(false)} onOk={() => void form.validateFields().then(({ body }) => noteMutation.mutate(body))}>
        <Form form={form} layout="vertical"><Form.Item name="body" rules={[{ required: true, min: 1, max: 4000 }]}><Input.TextArea rows={5} placeholder={copy.notePlaceholder} /></Form.Item></Form>
      </Modal>
    </div>
  )
}
