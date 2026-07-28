import { ArrowLeftOutlined, BellOutlined, CheckSquareOutlined, DeleteOutlined, LockOutlined, MessageOutlined, UnlockOutlined } from "@ant-design/icons"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Alert, Avatar, Button, Card, Col, Descriptions, Form, Input, List, Modal, Row, Space, Statistic, Tag, Timeline, Typography, message } from "antd"
import { useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { apiRequest } from "../../api/client"
import type { CustomerDetail } from "../../api/types"
import { useAuth } from "../../auth/AuthProvider"
import { LinkedCard } from "../../components/LinkedCard"
import { PageHeader } from "../../components/PageHeader"
import { QueryState } from "../../components/QueryState"
import { useLanguage } from "../../i18n/LanguageProvider"
import { domainLabel } from "../../i18n/domain"
import { dateTime, money } from "../../utils/format"

export function CustomerDetailPage() {
  const { customerId } = useParams()
  const navigate = useNavigate()
  const { locale } = useLanguage()
  const { hasPermission } = useAuth()
  const client = useQueryClient()
  const [noteOpen, setNoteOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [form] = Form.useForm<{ body: string }>()
  const [deleteForm] = Form.useForm<{ confirmation: string }>()
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
  const deleteMutation = useMutation({
    mutationFn: (customer: CustomerDetail) => apiRequest<void>(`/customers/${customer.id}`, {
      method: "DELETE",
      body: JSON.stringify({ confirmation: "DELETE", expected_updated_at: customer.updated_at }),
    }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["customers"] })
      void message.success(locale === "ru" ? "Профиль клиента полностью удалён" : "Customer profile permanently deleted")
      navigate("/customers")
    },
    onError: (error: Error) => void message.error(error.message),
  })
  const pushTestMutation = useMutation({
    mutationFn: () => apiRequest<{ accepted: boolean; status: string }>(`/customers/${customerId}/push-test`, { method: "POST" }),
    onSuccess: (result) => {
      void query.refetch()
      if (result.accepted) {
        void message.success(locale === "ru" ? "Expo принял тестовое уведомление" : "Expo accepted the test notification")
      } else {
        void message.warning(locale === "ru" ? "Отправка невозможна: у клиента нет действующего push-токена" : "Cannot send: the customer has no valid push token")
      }
    },
    onError: (error: Error) => void message.error(error.message),
  })
  const customer = query.data
  const copy = locale === "ru"
    ? { description: "Карточка клиента 360°", back: "К списку", block: "Заблокировать", unblock: "Разблокировать", delete: "Удалить профиль", deleteTitle: "Полностью удалить профиль?", deleteWarning: "Это необратимо: будут удалены аккаунт, заказы, корзина, лиды, переписки поддержки, AI-история, события, устройства, бонусы, аватар и файлы поддержки. Отзывы и публичные сообщения останутся без связи с профилем. Если пользователь является сотрудником, сначала удалите его доступ к админке.", deletePrompt: "Для подтверждения введите DELETE", note: "Добавить заметку", task: "Поставить задачу", revenue: "Выручка", orders: "Заказы", basket: "Корзина", views: "Просмотры", profile: "Профиль", activity: "Активность и интересы", intelligence: "Аналитика клиента", timeline: "Лента событий", devices: "Устройства", attribution: "Атрибуция и согласия", referrals: "Реферальная программа", notes: "Внутренние заметки", noNotes: "Заметок пока нет", noEvents: "Событий пока нет", noteTitle: "Новая заметка", notePlaceholder: "Контекст для коллег…", save: "Сохранить", cancel: "Отмена", pushReady: "Готов к отправке", pushNoToken: "Нет push-токена", pushDenied: "Push запрещён на устройстве", pushUnknown: "Статус push неизвестен", pushTest: "Отправить тест", lastPush: "Последняя отправка", lastToken: "Токен обновлён", active: "Активен", blocked: "Заблокирован", verified: "Подтверждён", sessions: "сессий", pushPermission: "Разрешение push", phone: "Телефон" }
    : { description: "360° customer profile", back: "Back", block: "Block", unblock: "Unblock", delete: "Delete profile", deleteTitle: "Permanently delete this profile?", deleteWarning: "This cannot be undone. The account, orders, cart, leads, support conversations, AI history, events, devices, benefits, avatar, and support files will be deleted. Reviews and public messages will remain without a profile link. If the user is a staff member, remove their admin access first.", deletePrompt: "Type DELETE to confirm", note: "Add note", task: "Create task", revenue: "Revenue", orders: "Orders", basket: "Basket", views: "Views", profile: "Profile", activity: "Activity & interests", intelligence: "Customer intelligence", timeline: "Event timeline", devices: "Devices", attribution: "Attribution & consent", referrals: "Referral program", notes: "Internal notes", noNotes: "No notes yet", noEvents: "No events yet", noteTitle: "New note", notePlaceholder: "Context for your team…", save: "Save", cancel: "Cancel", pushReady: "Ready to send", pushNoToken: "No push token", pushDenied: "Push denied on device", pushUnknown: "Push status unknown", pushTest: "Send test", lastPush: "Last dispatch", lastToken: "Token updated", active: "Active", blocked: "Blocked", verified: "Verified", sessions: "sessions", pushPermission: "Push permission", phone: "Phone" }
  const pushStatusText = {
    ready: copy.pushReady,
    no_token: copy.pushNoToken,
    permission_denied: copy.pushDenied,
    unknown: copy.pushUnknown,
  }[customer?.push_delivery_status || "unknown"]
  const customerOrdersPath = customer && hasPermission("orders.read")
    ? `/sales/orders?q=${encodeURIComponent(customer.email || customer.phone_number || `${customer.name} ${customer.surname}`.trim())}`
    : undefined
  const eventEntityPath = (entityType: string | null, entityId: string | number | null) => {
    if (!entityType || !entityId) return undefined
    if (entityType === "order" && hasPermission("orders.read")) return `/sales/orders/${entityId}`
    if (entityType === "product" && hasPermission("catalog.read")) return `/catalog/products?product_id=${entityId}`
    return undefined
  }

  return (
    <div className="page-stack">
      <PageHeader
        title={customer ? `${customer.name} ${customer.surname}` : locale === "ru" ? "Клиент" : "Customer"}
        description={copy.description}
        actions={<Space wrap><Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/customers")}>{copy.back}</Button>{customer && hasPermission("tasks.manage") ? <Button icon={<CheckSquareOutlined />} onClick={() => navigate(`/tasks?customer_id=${customer.id}&new=1`)}>{copy.task}</Button> : null}{customer && hasPermission("customers.manage") ? <Button danger={customer.is_active} icon={customer.is_active ? <LockOutlined /> : <UnlockOutlined />} loading={statusMutation.isPending} onClick={() => statusMutation.mutate(customer)}>{customer.is_active ? copy.block : copy.unblock}</Button> : null}{customer && hasPermission("customers.delete") ? <Button danger icon={<DeleteOutlined />} onClick={() => setDeleteOpen(true)}>{copy.delete}</Button> : null}</Space>}
      />
      <QueryState loading={query.isLoading} error={query.isError} onRetry={() => void query.refetch()} />
      {customer ? (
        <>
          <Row gutter={[16, 16]}>
            <Col xs={12} lg={6}><LinkedCard to={customerOrdersPath} linkLabel={copy.revenue}><Statistic title={copy.revenue} value={money(customer.paid_total, "RUB", locale)} /></LinkedCard></Col>
            <Col xs={12} lg={6}><LinkedCard to={customerOrdersPath} linkLabel={copy.orders}><Statistic title={copy.orders} value={customer.orders_count} /></LinkedCard></Col>
            <Col xs={12} lg={6}><Card><Statistic title={copy.basket} value={money(customer.basket_total, "RUB", locale)} suffix={`· ${customer.basket_items}`} /></Card></Col>
            <Col xs={12} lg={6}><Card><Statistic title={copy.views} value={customer.total_product_views} /></Card></Col>
          </Row>
          <Row gutter={[16, 16]}>
            <Col xs={24} xl={14}>
              <Card title={copy.profile}>
                <Space size={16} align="start" className="customer-identity"><Avatar size={64}>{`${customer.name[0] || ""}${customer.surname[0] || ""}`}</Avatar><div><Typography.Title level={4}>{customer.name} {customer.surname}</Typography.Title><Space><Tag color={customer.is_active ? "green" : "red"}>{customer.is_active ? copy.active : copy.blocked}</Tag>{customer.is_verified ? <Tag color="blue">{copy.verified}</Tag> : null}</Space></div></Space>
                <Descriptions column={{ xs: 1, md: 2 }}>
                  <Descriptions.Item label={locale === "ru" ? "Логин" : "Username"}>{customer.username || "—"}</Descriptions.Item>
                  <Descriptions.Item label="Email">{customer.email || "—"}</Descriptions.Item>
                  <Descriptions.Item label={copy.phone}>{customer.phone_number || "—"}</Descriptions.Item>
                  <Descriptions.Item label="Telegram">{customer.telegram_username ? `@${customer.telegram_username}` : "—"}</Descriptions.Item>
                  <Descriptions.Item label="amoCRM">{customer.contact_id || "—"}</Descriptions.Item>
                  <Descriptions.Item label="МойСклад">{customer.moysklad_counterparty_id || "—"}</Descriptions.Item>
                  <Descriptions.Item label={locale === "ru" ? "Последняя активность" : "Last active"}>{dateTime(customer.last_active_at, locale)}</Descriptions.Item>
                </Descriptions>
              </Card>
              <Card title={copy.activity}>
                <Row gutter={[16, 16]}><Col span={8}><Statistic title={locale === "ru" ? "Избранное" : "Favorites"} value={customer.favourites_count} /></Col><Col span={8}><Statistic title={locale === "ru" ? "В корзинах" : "Cart quantity"} value={customer.total_cart_quantity} /></Col><Col span={8}><Statistic title={locale === "ru" ? "Push-токены" : "Push tokens"} value={customer.push_tokens_count} /></Col></Row>
                <Alert
                  style={{ marginTop: 16 }}
                  type={customer.push_reachable ? "success" : customer.push_delivery_status === "permission_denied" ? "warning" : "error"}
                  showIcon
                  message={pushStatusText}
                  description={`${copy.lastToken}: ${dateTime(customer.last_push_token_at, locale)} · ${copy.lastPush}: ${dateTime(customer.last_push_dispatch_at, locale)}`}
                  action={hasPermission("customers.manage") ? <Button size="small" icon={<BellOutlined />} loading={pushTestMutation.isPending} disabled={!customer.push_reachable} onClick={() => pushTestMutation.mutate()}>{copy.pushTest}</Button> : null}
                />
              </Card>
              <Card title={copy.intelligence}>
                {customer.marketing_profile ? <>
                  <Space wrap style={{ marginBottom: 16 }}>
                    <Tag color="blue">{domainLabel(customer.marketing_profile.lifecycle_stage, locale)}</Tag>
                    <Tag>{domainLabel(customer.marketing_profile.last_platform, locale)} · {customer.marketing_profile.last_app_version || "—"}</Tag>
                    <Tag color={customer.marketing_profile.push_permission === "granted" ? "green" : "default"}>{copy.pushPermission}: {domainLabel(customer.marketing_profile.push_permission, locale)}</Tag>
                  </Space>
                  <Row gutter={[16, 16]}>
                    <Col xs={12} md={6}><Statistic title={locale === "ru" ? "Сессии" : "Sessions"} value={customer.marketing_profile.sessions_count} /></Col>
                    <Col xs={12} md={6}><Statistic title={locale === "ru" ? "События" : "Events"} value={customer.marketing_profile.total_events} /></Col>
                    <Col xs={12} md={6}><Statistic title={locale === "ru" ? "Оценка лида" : "Lead score"} value={customer.marketing_profile.lead_score} suffix="/100" /></Col>
                    <Col xs={12} md={6}><Statistic title={locale === "ru" ? "Поиски" : "Searches"} value={customer.marketing_profile.searches_count} /></Col>
                  </Row>
                </> : <Typography.Text type="secondary">{copy.noEvents}</Typography.Text>}
              </Card>
              <Card title={copy.devices}>
                <List
                  locale={{ emptyText: copy.noEvents }}
                  dataSource={customer.devices}
                  renderItem={(device) => <List.Item>
                    <List.Item.Meta
                      title={<Space><strong>{device.device_model || domainLabel(device.platform, locale)}</strong><Tag>{domainLabel(device.platform, locale)}</Tag><Tag color={device.push_permission === "granted" ? "green" : "default"}>{domainLabel(device.push_permission, locale)}</Tag></Space>}
                      description={`${device.app_version || "—"} (${device.app_build || "—"}) · ${device.os_version || "—"} · ${dateTime(device.last_seen_at, locale)}`}
                    />
                    <Typography.Text type="secondary">{device.sessions_count} {copy.sessions}</Typography.Text>
                  </List.Item>}
                />
              </Card>
              <Card title={copy.referrals}><Descriptions><Descriptions.Item label={locale === "ru" ? "Промокод" : "Promo code"}>{customer.promo_code || "—"}</Descriptions.Item><Descriptions.Item label={locale === "ru" ? "База скидки" : "Discount base"}>{money(customer.referral_discount_base_total, "RUB", locale)}</Descriptions.Item><Descriptions.Item label={locale === "ru" ? "Текущая скидка" : "Current discount"}>{customer.referral_discount_percent}%</Descriptions.Item></Descriptions></Card>
            </Col>
            <Col xs={24} xl={10}>
              <Card title={copy.timeline}>
                {customer.recent_events.length ? <Timeline items={customer.recent_events.slice(0, 20).map((event) => ({
                  color: ["order_created", "order_paid"].includes(event.event_name) ? "green" : event.event_name === "checkout_failed" ? "red" : "blue",
                  children: <div>
                    <Space wrap><strong>{domainLabel(event.event_name, locale)}</strong><Tag>{domainLabel(event.source, locale)}</Tag>{event.entity_type ? eventEntityPath(event.entity_type, event.entity_id) ? <Link to={eventEntityPath(event.entity_type, event.entity_id)!}>{domainLabel(event.entity_type, locale)} #{event.entity_id}</Link> : <Typography.Text type="secondary">{domainLabel(event.entity_type, locale)} #{event.entity_id}</Typography.Text> : null}</Space>
                    <div><Typography.Text type="secondary">{dateTime(event.occurred_at, locale)}</Typography.Text></div>
                    {Object.keys(event.properties).length ? <Typography.Text code>{JSON.stringify(event.properties)}</Typography.Text> : null}
                  </div>,
                }))} /> : <Typography.Text type="secondary">{copy.noEvents}</Typography.Text>}
              </Card>
              <Card title={copy.attribution}>
                <Descriptions column={1} size="small">
                  <Descriptions.Item label={locale === "ru" ? "Первое касание" : "First touch"}>{customer.attribution ? [customer.attribution.first_source, customer.attribution.first_medium, customer.attribution.first_campaign].filter(Boolean).join(" / ") || "—" : "—"}</Descriptions.Item>
                  <Descriptions.Item label={locale === "ru" ? "Последнее касание" : "Last touch"}>{customer.attribution ? [customer.attribution.last_source, customer.attribution.last_medium, customer.attribution.last_campaign].filter(Boolean).join(" / ") || "—" : "—"}</Descriptions.Item>
                  <Descriptions.Item label={locale === "ru" ? "Источник установки" : "Install source"}>{customer.attribution?.install_source || "—"}</Descriptions.Item>
                </Descriptions>
                <Space wrap>{customer.consents.map((consent) => <Tag key={consent.id} color={consent.is_granted ? "green" : "red"}>{domainLabel(consent.purpose, locale)} · {domainLabel(consent.channel, locale)}</Tag>)}</Space>
              </Card>
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
      <Modal
        open={deleteOpen}
        title={copy.deleteTitle}
        okText={copy.delete}
        cancelText={copy.cancel}
        okButtonProps={{ danger: true }}
        confirmLoading={deleteMutation.isPending}
        onCancel={() => { setDeleteOpen(false); deleteForm.resetFields() }}
        onOk={() => void deleteForm.validateFields().then(() => customer && deleteMutation.mutate(customer))}
      >
        <Alert type="error" showIcon message={copy.deleteWarning} style={{ marginBottom: 16 }} />
        <Form form={deleteForm} layout="vertical">
          <Form.Item
            name="confirmation"
            label={copy.deletePrompt}
            rules={[{
              validator: (_, value) => value === "DELETE"
                ? Promise.resolve()
                : Promise.reject(new Error(copy.deletePrompt)),
            }]}
          >
            <Input autoComplete="off" placeholder="DELETE" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
