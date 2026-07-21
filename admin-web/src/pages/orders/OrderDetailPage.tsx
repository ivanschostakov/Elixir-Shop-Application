import { ArrowLeftOutlined, CheckCircleOutlined, LinkOutlined, SendOutlined } from "@ant-design/icons"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Button, Card, Col, Descriptions, Divider, Row, Select, Space, Table, Tag, Timeline, Typography, message } from "antd"
import { useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { apiRequest } from "../../api/client"
import type { OrderDetail, OrderStatusCode } from "../../api/types"
import { useAuth } from "../../auth/AuthProvider"
import { PageHeader } from "../../components/PageHeader"
import { QueryState } from "../../components/QueryState"
import { useLanguage } from "../../i18n/LanguageProvider"
import { dateTime, money, statusColors, statusLabel } from "../../utils/format"

const allStatuses: OrderStatusCode[] = ["created", "invoice_sent", "paid", "waiting_response", "packaged", "sent", "delivered", "completed", "canceled", "refund_declined"]

export function OrderDetailPage() {
  const { orderId } = useParams()
  const navigate = useNavigate()
  const { locale } = useLanguage()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const [targetStatus, setTargetStatus] = useState<OrderStatusCode>()
  const query = useQuery({ queryKey: ["order", orderId], queryFn: () => apiRequest<OrderDetail>(`/orders/${orderId}`), enabled: Boolean(orderId) })
  const transition = useMutation({
    mutationFn: (order: OrderDetail) => apiRequest<OrderDetail>(`/orders/${order.id}/transition`, { method: "POST", body: JSON.stringify({ status_code: targetStatus, expected_updated_at: order.updated_at }) }),
    onSuccess: (data) => { queryClient.setQueryData(["order", orderId], data); setTargetStatus(undefined); void queryClient.invalidateQueries({ queryKey: ["orders"] }); void message.success(locale === "ru" ? "Статус обновлён" : "Status updated") },
    onError: (error: Error) => void message.error(error.message),
  })
  const order = query.data
  const copy = locale === "ru"
    ? { description: "Полная информация, оплата, доставка и связи с внешними системами", overview: "Обзор", customer: "Клиент и доставка", payment: "Оплата", integrations: "Интеграции", items: "Состав заказа", status: "Изменить статус", apply: "Применить", timeline: "История", subtotal: "Товары", delivery: "Доставка", total: "Итого", comment: "Комментарий" }
    : { description: "Order details, payment, fulfillment and external links", overview: "Overview", customer: "Customer & delivery", payment: "Payment", integrations: "Integrations", items: "Order items", status: "Change status", apply: "Apply", timeline: "Timeline", subtotal: "Items", delivery: "Delivery", total: "Total", comment: "Comment" }

  return (
    <div className="page-stack">
      <PageHeader
        title={order ? `${locale === "ru" ? "Заказ" : "Order"} ${order.order_code}` : locale === "ru" ? "Заказ" : "Order"}
        description={copy.description}
        actions={<Space><Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/sales/orders")}>{locale === "ru" ? "К списку" : "Back"}</Button>{order ? <Tag color={statusColors[order.status_code]}>{statusLabel(order.status_code, locale)}</Tag> : null}</Space>}
      />
      <QueryState loading={query.isLoading} error={query.isError} onRetry={() => void query.refetch()} />
      {order ? (
        <>
          {hasPermission("orders.transition") ? (
            <Card className="action-strip">
              <Space wrap><Select value={targetStatus} placeholder={copy.status} onChange={setTargetStatus} style={{ width: 220 }} options={allStatuses.filter((value) => value !== order.status_code).map((value) => ({ value, label: statusLabel(value, locale) }))} /><Button type="primary" icon={<SendOutlined />} disabled={!targetStatus} loading={transition.isPending} onClick={() => transition.mutate(order)}>{copy.apply}</Button></Space>
            </Card>
          ) : null}
          <Row gutter={[16, 16]}>
            <Col xs={24} xl={16}>
              <Card title={copy.overview}>
                <Descriptions column={{ xs: 1, md: 2 }}>
                  <Descriptions.Item label={copy.customer}>{order.customer.name} {order.customer.surname}</Descriptions.Item>
                  <Descriptions.Item label="Phone">{order.customer.phone_number || "—"}</Descriptions.Item>
                  <Descriptions.Item label="Email">{order.customer.email || "—"}</Descriptions.Item>
                  <Descriptions.Item label={copy.comment}>{order.comment || "—"}</Descriptions.Item>
                  <Descriptions.Item label={locale === "ru" ? "Адрес" : "Address"} span={2}>{String(order.address.full_address || order.delivery_string || "—")}</Descriptions.Item>
                </Descriptions>
                <Divider />
                <Space direction="vertical" style={{ width: "100%" }}>
                  <div className="amount-row"><span>{copy.subtotal}</span><strong>{money(order.basket_subtotal, order.currency, locale)}</strong></div>
                  <div className="amount-row"><span>{copy.delivery}</span><strong>{money(order.delivery_total, order.currency, locale)}</strong></div>
                  <div className="amount-row total"><span>{copy.total}</span><strong>{money(order.grand_total, order.currency, locale)}</strong></div>
                </Space>
              </Card>
              <Card title={copy.items}>
                <Table rowKey="id" pagination={false} dataSource={order.items} columns={[
                  { title: locale === "ru" ? "Товар" : "Product", key: "product", render: (_: unknown, item) => <div className="table-primary"><span>{item.product_name}</span><small>{item.product_sku} · {item.variant_name}</small></div> },
                  { title: locale === "ru" ? "Кол-во" : "Qty", dataIndex: "quantity", align: "center" as const },
                  { title: locale === "ru" ? "Цена" : "Price", key: "price", align: "right" as const, render: (_: unknown, item) => money(item.unit_price, order.currency, locale) },
                  { title: locale === "ru" ? "Сумма" : "Total", key: "total", align: "right" as const, render: (_: unknown, item) => <strong>{money(item.line_total, order.currency, locale)}</strong> },
                ]} />
              </Card>
            </Col>
            <Col xs={24} xl={8}>
              <Card title={copy.payment}>
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="Status"><Tag color={order.is_paid ? "green" : order.payment_error ? "red" : "orange"}>{order.payment_status}</Tag></Descriptions.Item>
                  <Descriptions.Item label="Method">{order.payment_method || "—"}</Descriptions.Item>
                  <Descriptions.Item label="Provider">{order.payment_provider || "—"}</Descriptions.Item>
                  <Descriptions.Item label="Invoice">{order.payment_invoice_id || "—"}</Descriptions.Item>
                  <Descriptions.Item label="Paid at">{dateTime(order.payment_paid_at, locale)}</Descriptions.Item>
                </Descriptions>
              </Card>
              <Card title={copy.integrations}>
                <Space direction="vertical">
                  <Typography.Text><LinkOutlined /> amoCRM: {order.amocrm_lead_id || "—"}</Typography.Text>
                  <Typography.Text><LinkOutlined /> МойСклад: {order.moysklad_customerorder_id || "—"}</Typography.Text>
                  <Typography.Text><LinkOutlined /> Delivery: {order.delivery_provider_ref || "—"}</Typography.Text>
                </Space>
              </Card>
              <Card title={copy.timeline}>
                <Timeline items={[
                  { color: "green", dot: <CheckCircleOutlined />, children: <><strong>{statusLabel(order.status_code, locale)}</strong><br /><Typography.Text type="secondary">{dateTime(order.updated_at, locale)}</Typography.Text></> },
                  { color: "gray", children: <>{locale === "ru" ? "Заказ создан" : "Order created"}<br /><Typography.Text type="secondary">{dateTime(order.created_at, locale)}</Typography.Text></> },
                ]} />
              </Card>
            </Col>
          </Row>
        </>
      ) : null}
    </div>
  )
}
