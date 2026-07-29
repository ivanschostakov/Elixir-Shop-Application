import { EyeOutlined, SearchOutlined, StarFilled } from "@ant-design/icons"
import { useQuery } from "@tanstack/react-query"
import { Alert, Avatar, Badge, Button, Card, Descriptions, Drawer, Empty, Image, Input, List, Select, Space, Table, Tag, Typography } from "antd"
import { useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { apiRequest, queryString } from "../../api/client"
import type { Page, Review, ReviewModerationEvent } from "../../api/types"
import { useAuth } from "../../auth/AuthProvider"
import { PageHeader } from "../../components/PageHeader"
import { parseVisibleColumns, TableToolbar, type TableColumnOption } from "../../components/TableToolbar"
import { useLanguage } from "../../i18n/LanguageProvider"
import { domainLabel } from "../../i18n/domain"
import { dateTime } from "../../utils/format"

type ReviewStatus = "pending" | "published" | "rejected"
const statusValues: ReviewStatus[] = ["pending", "published", "rejected"]
const flagColor = (score: number) => score >= 70 ? "red" : score >= 40 ? "orange" : "green"

export function ReviewsPage() {
  const { locale } = useLanguage()
  const { hasPermission } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const rawStatus = searchParams.get("status") as ReviewStatus | null
  const status = rawStatus && statusValues.includes(rawStatus) ? rawStatus : "pending"
  const rating = searchParams.get("rating") || undefined
  const flagged = searchParams.get("flagged") || undefined
  const q = searchParams.get("q") || ""
  const page = Math.max(Number(searchParams.get("page") || 1) || 1, 1)
  const pageSize = 50
  const [selected, setSelected] = useState<Review | null>(null)

  const copy = locale === "ru"
    ? {
      title: "Отзывы",
      description: "Отзывы приложения и сайта с единым статусом модерации.",
      authorityTitle: "Модерация выполняется в админке сайта Bitrix",
      authorityDescription: "Здесь доступен просмотр. Решение, ответ магазина и статус вложений автоматически синхронизируются из Bitrix в приложение.",
      pending: "Ожидают", published: "Опубликованы", rejected: "Отклонены", allRatings: "Все оценки", flaggedOnly: "С флагами", cleanOnly: "Без флагов", anyFlag: "Все",
      search: "Текст, автор, email или товар", author: "Автор", product: "Товар", rating: "Оценка", review: "Отзыв", flags: "Риски", date: "Дата", inspect: "Открыть",
      guest: "Гость", answer: "Публичный ответ магазина", internal: "Внутренний комментарий",
      privacy: "Email и IP видны только сотрудникам и не публикуются.",
      score: "Оценка спама", ip: "IP", appeal: "Апелляция", notified: "Клиент уведомлён", attachments: "Вложения", history: "История модерации", noHistory: "Истории пока нет",
      approved: "Одобрено", attachmentRejected: "Отклонено", attachmentPending: "На проверке", profanity: "мат", duplicate: "дубликат", suspiciousIp: "IP",
      anonymous: "Имя скрыто",
    }
    : {
      title: "Reviews",
      description: "App and website reviews with one moderation status.",
      authorityTitle: "Reviews are moderated in the Bitrix website admin",
      authorityDescription: "This page is read-only. The decision, store response, and attachment status are synchronized automatically from Bitrix to the app.",
      pending: "Pending", published: "Published", rejected: "Rejected", allRatings: "All ratings", flaggedOnly: "Flagged", cleanOnly: "Clean", anyFlag: "All",
      search: "Text, author, email or product", author: "Author", product: "Product", rating: "Rating", review: "Review", flags: "Risk", date: "Date", inspect: "Open",
      guest: "Guest", answer: "Public store response", internal: "Internal comment",
      privacy: "Email and IP are staff-only and never public.",
      score: "Spam score", ip: "IP", appeal: "Appeal", notified: "Customer notified", attachments: "Attachments", history: "Moderation history", noHistory: "No history yet",
      approved: "Approved", attachmentRejected: "Rejected", attachmentPending: "Pending", profanity: "profanity", duplicate: "duplicate", suspiciousIp: "IP",
      anonymous: "Name hidden",
    }

  const updateFilters = (values: Record<string, string | number | undefined>) => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current)
      Object.entries(values).forEach(([key, value]) => {
        if (value === undefined || value === "" || value === 1 || (key === "status" && value === "pending")) next.delete(key)
        else next.set(key, String(value))
      })
      return next
    })
  }

  const openReview = (review: Review) => {
    setSelected(review)
  }

  const query = useQuery({
    queryKey: ["reviews", status, page, rating, flagged, q],
    queryFn: () => apiRequest<Page<Review>>(`/reviews${queryString({ status, rating, flagged, q, limit: pageSize, offset: (page - 1) * pageSize })}`),
  })
  const history = useQuery({
    queryKey: ["review-history", selected?.id],
    queryFn: () => apiRequest<ReviewModerationEvent[]>(`/reviews/${selected?.id}/moderation-history`),
    enabled: Boolean(selected),
  })
  const tableColumns = [
    { title: copy.author, key: "author", render: (_: unknown, row: Review) => <Space><Avatar>{row.author_name[0] || "G"}</Avatar><div className="table-primary">{row.user_id && hasPermission("customers.read") ? <Link to={`/customers/${row.user_id}`}><strong>{row.author_name}</strong></Link> : <strong>{row.author_name}</strong>}<small>{row.author_email || copy.guest}</small>{row.hide_sender_name ? <Tag color="purple">{copy.anonymous}</Tag> : null}</div></Space> },
    { title: copy.product, dataIndex: "product_name", key: "product", render: (value: string, row: Review) => hasPermission("catalog.read") ? <Link to={`/catalog/products?product_id=${row.product_id}`}>{value}</Link> : value },
    { title: copy.rating, dataIndex: "value", key: "rating", render: (value: number) => <span className="rating-cell"><StarFilled /> {value}</span> },
    { title: copy.flags, key: "flags", render: (_: unknown, row: Review) => <Space size={4} wrap>
      <Tag color={flagColor(row.spam_score)}>{row.spam_score}</Tag>
      {row.profanity_flag ? <Tag color="red">{copy.profanity}</Tag> : null}
      {row.duplicate_flag ? <Tag color="orange">{copy.duplicate}</Tag> : null}
      {row.suspicious_ip_flag ? <Tag color="volcano">{copy.suspiciousIp}</Tag> : null}
      {row.attachment_items.some((item) => item.moderation_status === "pending") ? <Badge status="processing" text={copy.attachments} /> : null}
    </Space> },
    { title: copy.review, dataIndex: "text", key: "review", ellipsis: true, width: "28%", render: (value: string | null) => value || "—" },
    { title: copy.date, dataIndex: "created_at", key: "date", render: (value: string) => dateTime(value, locale) },
    { title: "", key: "action", align: "right" as const, render: (_: unknown, row: Review) => <Button icon={<EyeOutlined />} onClick={() => openReview(row)}>{copy.inspect}</Button> },
  ]
  const columnOptions: TableColumnOption[] = [
    { key: "author", label: copy.author, exportKeys: ["author", "email"] },
    { key: "product", label: copy.product, exportKeys: ["product"] },
    { key: "rating", label: copy.rating, exportKeys: ["rating"] },
    { key: "flags", label: copy.flags, exportKeys: ["spam_score"] },
    { key: "review", label: copy.review, exportKeys: ["text"] },
    { key: "date", label: copy.date, exportKeys: ["created_at"] },
    { key: "action", label: copy.inspect },
  ]
  const visibleColumns = parseVisibleColumns(searchParams.get("columns"), columnOptions.map((column) => column.key))
  const viewState = Object.fromEntries(Array.from(searchParams.entries()).filter(([key]) => key !== "page"))
  const statusOptions = [
    { value: "pending", label: `${copy.pending}${status === "pending" ? ` (${query.data?.total ?? 0})` : ""}` },
    { value: "published", label: copy.published },
    { value: "rejected", label: copy.rejected },
  ]

  return <div className="page-stack">
    <PageHeader title={copy.title} description={copy.description} />
    <Alert showIcon type="info" message={copy.authorityTitle} description={copy.authorityDescription} />
    <Card className="filter-card">
      <Space wrap>
        <Select value={status} options={statusOptions} style={{ width: 180 }} onChange={(value) => updateFilters({ status: value, page: 1 })} />
        <Select allowClear value={rating} placeholder={copy.allRatings} style={{ width: 150 }} options={[0, 1, 2, 3, 4, 5].map((value) => ({ value: String(value), label: `${value} ★` }))} onChange={(value) => updateFilters({ rating: value, page: 1 })} />
        <Select allowClear value={flagged} placeholder={copy.anyFlag} style={{ width: 150 }} options={[{ value: "true", label: copy.flaggedOnly }, { value: "false", label: copy.cleanOnly }]} onChange={(value) => updateFilters({ flagged: value, page: 1 })} />
        <Input allowClear prefix={<SearchOutlined />} value={q} placeholder={copy.search} onChange={(event) => updateFilters({ q: event.target.value, page: 1 })} />
      </Space>
    </Card>
    <TableToolbar
      resource="reviews"
      columns={columnOptions}
      visibleColumns={visibleColumns}
      onVisibleColumnsChange={(keys) => updateFilters({ columns: keys.length === columnOptions.length ? undefined : keys.join(","), page: 1 })}
      viewState={viewState}
      onApplyViewState={(state) => setSearchParams(state)}
      exportFilters={{ status, rating, flagged, q }}
    />
    <Table<Review>
      rowKey="id"
      loading={query.isLoading}
      dataSource={query.data?.items}
      pagination={{ current: page, pageSize, total: query.data?.total, showSizeChanger: false, onChange: (nextPage) => updateFilters({ page: nextPage }) }}
      locale={{ emptyText: <Empty description={locale === "ru" ? "Очередь пуста" : "Queue is empty"} /> }}
      columns={tableColumns.filter((column) => visibleColumns.includes(String(column.key)))}
    />
    <Drawer
      width={680}
      open={Boolean(selected)}
      title={copy.inspect}
      onClose={() => setSelected(null)}
    >
      {selected ? <Space direction="vertical" size={18} style={{ width: "100%" }}>
        <div className="review-author"><Avatar size={48}>{selected.author_name[0] || "G"}</Avatar><div><Typography.Title level={4}>{selected.user_id && hasPermission("customers.read") ? <Link to={`/customers/${selected.user_id}`}>{selected.author_name}</Link> : selected.author_name}</Typography.Title><Typography.Text type="secondary">{selected.author_email || copy.guest} · {dateTime(selected.created_at, locale)}</Typography.Text></div></div>
        <Descriptions size="small" column={2} bordered>
          <Descriptions.Item label={copy.product}>{hasPermission("catalog.read") ? <Link to={`/catalog/products?product_id=${selected.product_id}`}>{selected.product_name}</Link> : selected.product_name}</Descriptions.Item>
          <Descriptions.Item label={copy.rating}><span className="rating-cell"><StarFilled /> {selected.value}</span></Descriptions.Item>
          <Descriptions.Item label={copy.score}><Tag color={flagColor(selected.spam_score)}>{selected.spam_score}</Tag></Descriptions.Item>
          <Descriptions.Item label={copy.ip}>{selected.submitter_ip || "—"}</Descriptions.Item>
          <Descriptions.Item label={copy.appeal}>{domainLabel(selected.appeal_status, locale)}</Descriptions.Item>
          <Descriptions.Item label={copy.notified}>{selected.customer_notified_at ? dateTime(selected.customer_notified_at, locale) : "—"}</Descriptions.Item>
        </Descriptions>
        {(selected.profanity_flag || selected.duplicate_flag || selected.suspicious_ip_flag) ? <Alert type="warning" showIcon message={<Space wrap>
          {selected.profanity_flag ? <Tag color="red">{copy.profanity}</Tag> : null}
          {selected.duplicate_flag ? <Tag color="orange">{copy.duplicate}</Tag> : null}
          {selected.suspicious_ip_flag ? <Tag color="volcano">{copy.suspiciousIp}</Tag> : null}
        </Space>} /> : null}
        <Typography.Paragraph className="review-full-text">{selected.text || "—"}</Typography.Paragraph>
        {selected.attachment_items.length ? <div>
          <Typography.Text strong>{copy.attachments}</Typography.Text>
          <Image.PreviewGroup><div className="review-images">{selected.attachment_items.map((item) => <div className="moderated-image" key={item.id}>
            <Image src={item.url} width={124} height={124} />
            <Tag color={item.moderation_status === "approved" ? "green" : item.moderation_status === "rejected" ? "red" : "blue"}>
              {item.moderation_status === "approved" ? copy.approved : item.moderation_status === "rejected" ? copy.attachmentRejected : copy.attachmentPending}
            </Tag>
          </div>)}</div></Image.PreviewGroup>
        </div> : null}
        <div><Typography.Text strong>{copy.answer}</Typography.Text><Typography.Paragraph>{selected.answer || "—"}</Typography.Paragraph></div>
        <div><Typography.Text strong>{copy.internal}</Typography.Text><Typography.Paragraph>{selected.internal_moderation_comment || "—"}</Typography.Paragraph></div>
        <Typography.Text type="secondary">{copy.privacy}</Typography.Text>
        <Card size="small" title={copy.history}>
          <List
            loading={history.isLoading}
            dataSource={history.data || []}
            locale={{ emptyText: copy.noHistory }}
            renderItem={(event) => <List.Item>
              <List.Item.Meta
                title={<Space><Tag>{domainLabel(event.action, locale)}</Tag><span>{event.actor_name || "—"}</span></Space>}
                description={<Space direction="vertical" size={2}><span>{dateTime(event.created_at, locale)}</span>{event.comment ? <span>{event.comment}</span> : null}</Space>}
              />
            </List.Item>}
          />
        </Card>
      </Space> : null}
    </Drawer>
  </div>
}
