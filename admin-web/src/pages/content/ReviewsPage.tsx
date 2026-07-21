import { CheckOutlined, CloseOutlined, EyeOutlined, StarFilled } from "@ant-design/icons"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Avatar, Button, Card, Drawer, Empty, Image, Input, Segmented, Space, Table, Tag, Typography, message } from "antd"
import { useState } from "react"
import { apiRequest, queryString } from "../../api/client"
import type { Page, Review } from "../../api/types"
import { useAuth } from "../../auth/AuthProvider"
import { PageHeader } from "../../components/PageHeader"
import { useLanguage } from "../../i18n/LanguageProvider"
import { dateTime } from "../../utils/format"

type ReviewStatus = "pending" | "published" | "rejected"

export function ReviewsPage() {
  const { locale } = useLanguage()
  const { hasPermission } = useAuth()
  const client = useQueryClient()
  const [status, setStatus] = useState<ReviewStatus>("pending")
  const [selected, setSelected] = useState<Review | null>(null)
  const [answer, setAnswer] = useState("")
  const query = useQuery({ queryKey: ["reviews", status], queryFn: () => apiRequest<Page<Review>>(`/reviews${queryString({ status, limit: 100 })}`) })
  const moderate = useMutation({
    mutationFn: ({ review, action }: { review: Review; action: "publish" | "reject" }) => apiRequest<Review>(`/reviews/${review.id}/moderation`, { method: "PATCH", body: JSON.stringify({ action, answer: answer.trim() || null, expected_updated_at: review.updated_at }) }),
    onSuccess: () => { setSelected(null); setAnswer(""); void client.invalidateQueries({ queryKey: ["reviews"] }); void client.invalidateQueries({ queryKey: ["dashboard"] }); void message.success(locale === "ru" ? "Решение сохранено" : "Decision saved") },
    onError: (error: Error) => void message.error(error.message),
  })
  const copy = locale === "ru"
    ? { title: "Модерация отзывов", description: "Новые отзывы не попадают на витрину до публикации", pending: "Ожидают", published: "Опубликованы", rejected: "Отклонены", author: "Автор", product: "Товар", rating: "Оценка", review: "Отзыв", date: "Дата", inspect: "Проверить", guest: "Гость", answer: "Ответ магазина", answerPlaceholder: "Необязательный публичный ответ…", publish: "Опубликовать", reject: "Отклонить", privacy: "Email гостя виден только сотрудникам и не публикуется." }
    : { title: "Review moderation", description: "New reviews stay private until an administrator publishes them", pending: "Pending", published: "Published", rejected: "Rejected", author: "Author", product: "Product", rating: "Rating", review: "Review", date: "Date", inspect: "Review", guest: "Guest", answer: "Store response", answerPlaceholder: "Optional public response…", publish: "Publish", reject: "Reject", privacy: "Guest email is visible only to staff and is never published." }
  const statusOptions = [{ value: "pending", label: `${copy.pending} (${status === "pending" ? query.data?.total ?? 0 : ""})` }, { value: "published", label: copy.published }, { value: "rejected", label: copy.rejected }]

  return <div className="page-stack">
    <PageHeader title={copy.title} description={copy.description} />
    <Card className="filter-card"><Segmented value={status} options={statusOptions} onChange={(value) => setStatus(value as ReviewStatus)} /></Card>
    <Table<Review> rowKey="id" loading={query.isLoading} dataSource={query.data?.items} locale={{ emptyText: <Empty description={locale === "ru" ? "Очередь пуста" : "Queue is empty"} /> }} columns={[
      { title: copy.author, key: "author", render: (_: unknown, row) => <Space><Avatar>{row.author_name[0] || "G"}</Avatar><div className="table-primary"><strong>{row.author_name}</strong><small>{row.author_email || copy.guest}</small></div></Space> },
      { title: copy.product, dataIndex: "product_name" },
      { title: copy.rating, dataIndex: "value", render: (value: number) => <span className="rating-cell"><StarFilled /> {value}</span> },
      { title: copy.review, dataIndex: "text", ellipsis: true, width: "32%", render: (value: string | null) => value || "—" },
      { title: copy.date, dataIndex: "created_at", render: (value: string) => dateTime(value, locale) },
      { title: "", align: "right", render: (_: unknown, row) => <Button icon={<EyeOutlined />} onClick={() => { setSelected(row); setAnswer(row.answer || "") }}>{copy.inspect}</Button> },
    ]} />
    <Drawer width={560} open={Boolean(selected)} title={copy.inspect} onClose={() => setSelected(null)} extra={selected && hasPermission("reviews.moderate") ? <Space><Button danger icon={<CloseOutlined />} loading={moderate.isPending} onClick={() => moderate.mutate({ review: selected, action: "reject" })}>{copy.reject}</Button><Button type="primary" icon={<CheckOutlined />} loading={moderate.isPending} onClick={() => moderate.mutate({ review: selected, action: "publish" })}>{copy.publish}</Button></Space> : null}>
      {selected ? <Space direction="vertical" size={20} style={{ width: "100%" }}>
        <div className="review-author"><Avatar size={48}>{selected.author_name[0] || "G"}</Avatar><div><Typography.Title level={4}>{selected.author_name}</Typography.Title><Typography.Text type="secondary">{selected.author_email || copy.guest} · {dateTime(selected.created_at, locale)}</Typography.Text></div></div>
        <div><Typography.Text type="secondary">{copy.product}</Typography.Text><Typography.Title level={5}>{selected.product_name}</Typography.Title><div className="review-stars">{Array.from({ length: 5 }, (_, index) => <StarFilled key={index} className={index < selected.value ? "filled" : ""} />)}</div></div>
        <Typography.Paragraph className="review-full-text">{selected.text || "—"}</Typography.Paragraph>
        {selected.attachments.length ? <Image.PreviewGroup><div className="review-images">{selected.attachments.map((source) => <Image key={source} src={source} width={120} height={120} />)}</div></Image.PreviewGroup> : null}
        <div><Typography.Text strong>{copy.answer}</Typography.Text><Input.TextArea rows={5} value={answer} maxLength={4000} placeholder={copy.answerPlaceholder} onChange={(event) => setAnswer(event.target.value)} /></div>
        <Typography.Text type="secondary">{copy.privacy}</Typography.Text>
      </Space> : null}
    </Drawer>
  </div>
}
