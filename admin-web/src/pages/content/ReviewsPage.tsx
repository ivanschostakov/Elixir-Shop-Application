import { CheckOutlined, CloseOutlined, EyeOutlined, SearchOutlined, StarFilled, StopOutlined } from "@ant-design/icons"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Alert, Avatar, Badge, Button, Card, Descriptions, Drawer, Empty, Image, Input, List, Select, Space, Table, Tag, Typography, message } from "antd"
import { useState } from "react"
import { useSearchParams } from "react-router-dom"
import { apiRequest, queryString } from "../../api/client"
import type { Page, Review, ReviewModerationEvent } from "../../api/types"
import { useAuth } from "../../auth/AuthProvider"
import { PageHeader } from "../../components/PageHeader"
import { parseVisibleColumns, TableToolbar, type TableColumnOption } from "../../components/TableToolbar"
import { useLanguage } from "../../i18n/LanguageProvider"
import { dateTime } from "../../utils/format"

type ReviewStatus = "pending" | "published" | "rejected"
type ReviewAction = "publish" | "reject" | "restore"
type AttachmentStatus = "approved" | "rejected" | "pending"

const statusValues: ReviewStatus[] = ["pending", "published", "rejected"]
const flagColor = (score: number) => score >= 70 ? "red" : score >= 40 ? "orange" : "green"

export function ReviewsPage() {
  const { locale } = useLanguage()
  const { hasPermission } = useAuth()
  const client = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const rawStatus = searchParams.get("status") as ReviewStatus | null
  const status = rawStatus && statusValues.includes(rawStatus) ? rawStatus : "pending"
  const rating = searchParams.get("rating") || undefined
  const flagged = searchParams.get("flagged") || undefined
  const q = searchParams.get("q") || ""
  const page = Math.max(Number(searchParams.get("page") || 1) || 1, 1)
  const pageSize = 50
  const [selected, setSelected] = useState<Review | null>(null)
  const [selectedReviews, setSelectedReviews] = useState<Review[]>([])
  const [answer, setAnswer] = useState("")
  const [internalComment, setInternalComment] = useState("")
  const [attachmentStatuses, setAttachmentStatuses] = useState<Record<number, AttachmentStatus>>({})

  const copy = locale === "ru"
    ? {
      title: "Модерация отзывов",
      description: "Любой клиент или гость может оставить отзыв; на витрину он попадёт только после проверки.",
      pending: "Ожидают", published: "Опубликованы", rejected: "Отклонены", allRatings: "Все оценки", flaggedOnly: "С флагами", cleanOnly: "Без флагов", anyFlag: "Все",
      search: "Текст, автор, email или товар", author: "Автор", product: "Товар", rating: "Оценка", review: "Отзыв", flags: "Риски", date: "Дата", inspect: "Проверить",
      guest: "Гость", answer: "Публичный ответ магазина", answerPlaceholder: "Необязательный ответ, который увидят пользователи…", internal: "Внутренний комментарий", internalPlaceholder: "Причина решения, подозрения, заметка для команды…",
      publish: "Опубликовать", reject: "Отклонить", restore: "Вернуть на модерацию", spamReject: "Отклонить спам", privacy: "Email и IP видны только сотрудникам и не публикуются.",
      score: "Spam score", ip: "IP", appeal: "Апелляция", notified: "Клиент уведомлён", attachments: "Вложения", history: "История модерации", noHistory: "Истории пока нет",
      approved: "Одобрено", attachmentRejected: "Отклонено", attachmentPending: "На проверке", profanity: "мат", duplicate: "дубликат", suspiciousIp: "IP", saved: "Решение сохранено",
    }
    : {
      title: "Review moderation",
      description: "Every customer or guest can leave a review; it appears publicly only after approval.",
      pending: "Pending", published: "Published", rejected: "Rejected", allRatings: "All ratings", flaggedOnly: "Flagged", cleanOnly: "Clean", anyFlag: "All",
      search: "Text, author, email or product", author: "Author", product: "Product", rating: "Rating", review: "Review", flags: "Risk", date: "Date", inspect: "Review",
      guest: "Guest", answer: "Public store response", answerPlaceholder: "Optional response visible to users…", internal: "Internal comment", internalPlaceholder: "Decision reason, suspicion, note for the team…",
      publish: "Publish", reject: "Reject", restore: "Restore to moderation", spamReject: "Reject spam", privacy: "Email and IP are staff-only and never public.",
      score: "Spam score", ip: "IP", appeal: "Appeal", notified: "Customer notified", attachments: "Attachments", history: "Moderation history", noHistory: "No history yet",
      approved: "Approved", attachmentRejected: "Rejected", attachmentPending: "Pending", profanity: "profanity", duplicate: "duplicate", suspiciousIp: "IP", saved: "Decision saved",
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
    setAnswer(review.answer || "")
    setInternalComment(review.internal_moderation_comment || "")
    setAttachmentStatuses(Object.fromEntries(review.attachment_items.map((item) => [item.id, item.moderation_status])))
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
  const moderate = useMutation({
    mutationFn: ({ review, action }: { review: Review; action: ReviewAction }) => apiRequest<Review>(`/reviews/${review.id}/moderation`, {
      method: "PATCH",
      body: JSON.stringify({
        action,
        answer: answer.trim() || null,
        internal_comment: internalComment.trim() || null,
        attachment_statuses: attachmentStatuses,
        expected_updated_at: review.updated_at,
      }),
    }),
    onSuccess: () => {
      setSelected(null)
      setAnswer("")
      setInternalComment("")
      setAttachmentStatuses({})
      void client.invalidateQueries({ queryKey: ["reviews"] })
      void client.invalidateQueries({ queryKey: ["review-history"] })
      void client.invalidateQueries({ queryKey: ["dashboard"] })
      void message.success(copy.saved)
    },
    onError: (error: Error) => void message.error(error.message),
  })
  const bulkModerate = useMutation({
    mutationFn: (action: "publish" | "reject") => apiRequest<Review[]>("/reviews/bulk-moderation", {
      method: "POST",
      body: JSON.stringify({ action, internal_comment: internalComment.trim() || null, items: selectedReviews.map((review) => ({ id: review.id, expected_updated_at: review.updated_at })) }),
    }),
    onSuccess: () => {
      setSelectedReviews([])
      void client.invalidateQueries({ queryKey: ["reviews"] })
      void client.invalidateQueries({ queryKey: ["dashboard"] })
      void message.success(locale === "ru" ? "Отзывы обработаны" : "Reviews moderated")
    },
    onError: (error: Error) => void message.error(error.message),
  })
  const bulkRejectSpam = useMutation({
    mutationFn: () => apiRequest<Review[]>("/reviews/bulk-reject-spam", { method: "POST" }),
    onSuccess: (items) => {
      setSelectedReviews([])
      void client.invalidateQueries({ queryKey: ["reviews"] })
      void client.invalidateQueries({ queryKey: ["dashboard"] })
      void message.success(locale === "ru" ? `Спам отклонён: ${items.length}` : `Spam rejected: ${items.length}`)
    },
    onError: (error: Error) => void message.error(error.message),
  })

  const tableColumns = [
    { title: copy.author, key: "author", render: (_: unknown, row: Review) => <Space><Avatar>{row.author_name[0] || "G"}</Avatar><div className="table-primary"><strong>{row.author_name}</strong><small>{row.author_email || copy.guest}</small></div></Space> },
    { title: copy.product, dataIndex: "product_name", key: "product" },
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
    <Card className="filter-card">
      <Space wrap>
        <Select value={status} options={statusOptions} style={{ width: 180 }} onChange={(value) => { setSelectedReviews([]); updateFilters({ status: value, page: 1 }) }} />
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
      onApplyViewState={(state) => { setSelectedReviews([]); setSearchParams(state) }}
      exportFilters={{ status, rating, flagged, q }}
      selectedIds={selectedReviews.map((review) => review.id)}
      onClearSelection={() => setSelectedReviews([])}
      bulkActions={hasPermission("reviews.moderate") ? <Space size={4}>
        <Button size="small" icon={<CheckOutlined />} loading={bulkModerate.isPending} disabled={!selectedReviews.length} onClick={() => bulkModerate.mutate("publish")}>{copy.publish}</Button>
        <Button size="small" danger icon={<CloseOutlined />} loading={bulkModerate.isPending} disabled={!selectedReviews.length} onClick={() => bulkModerate.mutate("reject")}>{copy.reject}</Button>
        <Button size="small" danger icon={<StopOutlined />} loading={bulkRejectSpam.isPending} onClick={() => bulkRejectSpam.mutate()}>{copy.spamReject}</Button>
      </Space> : null}
    />
    <Table<Review>
      rowKey="id"
      loading={query.isLoading}
      dataSource={query.data?.items}
      rowSelection={{ selectedRowKeys: selectedReviews.map((review) => review.id), onChange: (_keys, rows) => setSelectedReviews(rows) }}
      pagination={{ current: page, pageSize, total: query.data?.total, showSizeChanger: false, onChange: (nextPage) => { setSelectedReviews([]); updateFilters({ page: nextPage }) } }}
      locale={{ emptyText: <Empty description={locale === "ru" ? "Очередь пуста" : "Queue is empty"} /> }}
      columns={tableColumns.filter((column) => visibleColumns.includes(String(column.key)))}
    />
    <Drawer
      width={680}
      open={Boolean(selected)}
      title={copy.inspect}
      onClose={() => setSelected(null)}
      extra={selected && hasPermission("reviews.moderate") ? <Space>
        {selected.status === "rejected" ? <Button icon={<StopOutlined />} loading={moderate.isPending} onClick={() => moderate.mutate({ review: selected, action: "restore" })}>{copy.restore}</Button> : null}
        <Button danger icon={<CloseOutlined />} loading={moderate.isPending} onClick={() => moderate.mutate({ review: selected, action: "reject" })}>{copy.reject}</Button>
        <Button type="primary" icon={<CheckOutlined />} loading={moderate.isPending} onClick={() => moderate.mutate({ review: selected, action: "publish" })}>{copy.publish}</Button>
      </Space> : null}
    >
      {selected ? <Space direction="vertical" size={18} style={{ width: "100%" }}>
        <div className="review-author"><Avatar size={48}>{selected.author_name[0] || "G"}</Avatar><div><Typography.Title level={4}>{selected.author_name}</Typography.Title><Typography.Text type="secondary">{selected.author_email || copy.guest} · {dateTime(selected.created_at, locale)}</Typography.Text></div></div>
        <Descriptions size="small" column={2} bordered>
          <Descriptions.Item label={copy.product}>{selected.product_name}</Descriptions.Item>
          <Descriptions.Item label={copy.rating}><span className="rating-cell"><StarFilled /> {selected.value}</span></Descriptions.Item>
          <Descriptions.Item label={copy.score}><Tag color={flagColor(selected.spam_score)}>{selected.spam_score}</Tag></Descriptions.Item>
          <Descriptions.Item label={copy.ip}>{selected.submitter_ip || "—"}</Descriptions.Item>
          <Descriptions.Item label={copy.appeal}>{selected.appeal_status}</Descriptions.Item>
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
            <Select
              size="small"
              value={attachmentStatuses[item.id] || item.moderation_status}
              options={[
                { value: "approved", label: copy.approved },
                { value: "pending", label: copy.attachmentPending },
                { value: "rejected", label: copy.attachmentRejected },
              ]}
              onChange={(value) => setAttachmentStatuses((current) => ({ ...current, [item.id]: value }))}
            />
          </div>)}</div></Image.PreviewGroup>
        </div> : null}
        <div><Typography.Text strong>{copy.answer}</Typography.Text><Input.TextArea rows={4} value={answer} maxLength={4000} placeholder={copy.answerPlaceholder} onChange={(event) => setAnswer(event.target.value)} /></div>
        <div><Typography.Text strong>{copy.internal}</Typography.Text><Input.TextArea rows={3} value={internalComment} maxLength={4000} placeholder={copy.internalPlaceholder} onChange={(event) => setInternalComment(event.target.value)} /></div>
        <Typography.Text type="secondary">{copy.privacy}</Typography.Text>
        <Card size="small" title={copy.history}>
          <List
            loading={history.isLoading}
            dataSource={history.data || []}
            locale={{ emptyText: copy.noHistory }}
            renderItem={(event) => <List.Item>
              <List.Item.Meta
                title={<Space><Tag>{event.action}</Tag><span>{event.actor_name || "—"}</span></Space>}
                description={<Space direction="vertical" size={2}><span>{dateTime(event.created_at, locale)}</span>{event.comment ? <span>{event.comment}</span> : null}</Space>}
              />
            </List.Item>}
          />
        </Card>
      </Space> : null}
    </Drawer>
  </div>
}
