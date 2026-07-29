import {
  CheckOutlined,
  CloseOutlined,
  EyeOutlined,
  QuestionCircleOutlined,
  SearchOutlined,
} from "@ant-design/icons"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  Alert,
  Avatar,
  Button,
  Card,
  Descriptions,
  Drawer,
  Empty,
  Input,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd"
import { useEffect, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"

import { apiRequest, queryString } from "../../api/client"
import type { Page, ProductQuestion } from "../../api/types"
import { useAuth } from "../../auth/AuthProvider"
import { PageHeader } from "../../components/PageHeader"
import { useLanguage } from "../../i18n/LanguageProvider"
import { dateTime } from "../../utils/format"

type QuestionStatus = ProductQuestion["status"]
const statusValues: QuestionStatus[] = ["pending", "published", "rejected"]

export function QuestionsPage() {
  const { locale } = useLanguage()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const rawStatus = searchParams.get("status") as QuestionStatus | null
  const status = rawStatus && statusValues.includes(rawStatus) ? rawStatus : "pending"
  const q = searchParams.get("q") || ""
  const page = Math.max(Number(searchParams.get("page") || 1) || 1, 1)
  const pageSize = 50
  const [selected, setSelected] = useState<ProductQuestion | null>(null)
  const [answer, setAnswer] = useState("")
  const [internalComment, setInternalComment] = useState("")
  const copy = locale === "ru"
    ? {
      title: "Вопросы",
      description: "Вопросы покупателей модерируются только здесь и не отправляются в Bitrix.",
      localTitle: "Отдельная очередь приложения",
      localDescription: "Публикация, отклонение и ответ магазина остаются внутри приложения.",
      pending: "Ожидают",
      published: "Опубликованы",
      rejected: "Отклонены",
      search: "Вопрос, ответ, автор или товар",
      author: "Автор",
      guest: "Гость",
      product: "Товар",
      question: "Вопрос",
      answer: "Публичный ответ магазина",
      internal: "Внутренний комментарий",
      date: "Дата",
      inspect: "Открыть",
      publish: "Опубликовать",
      reject: "Отклонить",
      saved: "Решение сохранено",
      queueEmpty: "Очередь пуста",
      moderation: "Модерация вопроса",
      status: "Статус",
    }
    : {
      title: "Questions",
      description: "Customer questions are moderated only here and are never sent to Bitrix.",
      localTitle: "Separate app queue",
      localDescription: "Publishing, rejection, and the store answer stay inside the app.",
      pending: "Pending",
      published: "Published",
      rejected: "Rejected",
      search: "Question, answer, author or product",
      author: "Author",
      guest: "Guest",
      product: "Product",
      question: "Question",
      answer: "Public store answer",
      internal: "Internal comment",
      date: "Date",
      inspect: "Open",
      publish: "Publish",
      reject: "Reject",
      saved: "Decision saved",
      queueEmpty: "Queue is empty",
      moderation: "Question moderation",
      status: "Status",
    }

  const updateFilters = (values: Record<string, string | number | undefined>) => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current)
      Object.entries(values).forEach(([key, value]) => {
        if (value === undefined || value === "" || value === 1 || (key === "status" && value === "pending")) {
          next.delete(key)
        } else {
          next.set(key, String(value))
        }
      })
      return next
    })
  }

  const query = useQuery({
    queryKey: ["product-questions", status, page, q],
    queryFn: () => apiRequest<Page<ProductQuestion>>(
      `/questions${queryString({
        status,
        q,
        limit: pageSize,
        offset: (page - 1) * pageSize,
      })}`,
    ),
  })

  useEffect(() => {
    setAnswer(selected?.answer || "")
    setInternalComment(selected?.internal_moderation_comment || "")
  }, [selected])

  const moderate = useMutation({
    mutationFn: (action: "publish" | "reject") => apiRequest<ProductQuestion>(
      `/questions/${selected?.id}/moderation`,
      {
        method: "PATCH",
        body: JSON.stringify({
          action,
          answer: answer.trim() || null,
          internal_comment: internalComment.trim() || null,
          expected_updated_at: selected?.updated_at,
        }),
      },
    ),
    onSuccess: () => {
      setSelected(null)
      void queryClient.invalidateQueries({ queryKey: ["product-questions"] })
      void message.success(copy.saved)
    },
    onError: (error: Error) => void message.error(error.message),
  })

  const statusOptions = [
    { value: "pending", label: `${copy.pending}${status === "pending" ? ` (${query.data?.total ?? 0})` : ""}` },
    { value: "published", label: copy.published },
    { value: "rejected", label: copy.rejected },
  ]
  const statusColor = (value: QuestionStatus) => value === "published"
    ? "green"
    : value === "rejected"
      ? "red"
      : "gold"

  return (
    <div className="page-stack">
      <PageHeader title={copy.title} description={copy.description} />
      <Alert
        showIcon
        type="info"
        message={copy.localTitle}
        description={copy.localDescription}
      />
      <Card className="filter-card">
        <Space wrap>
          <Select
            value={status}
            options={statusOptions}
            style={{ width: 180 }}
            onChange={(value) => updateFilters({ status: value, page: 1 })}
          />
          <Input
            allowClear
            prefix={<SearchOutlined />}
            value={q}
            placeholder={copy.search}
            onChange={(event) => updateFilters({ q: event.target.value, page: 1 })}
          />
        </Space>
      </Card>
      <Table<ProductQuestion>
        rowKey="id"
        loading={query.isLoading}
        dataSource={query.data?.items}
        pagination={{
          current: page,
          pageSize,
          total: query.data?.total,
          showSizeChanger: false,
          onChange: (nextPage) => updateFilters({ page: nextPage }),
        }}
        locale={{ emptyText: <Empty description={copy.queueEmpty} /> }}
        columns={[
          {
            title: copy.author,
            key: "author",
            render: (_value, row) => (
              <Space>
                <Avatar icon={<QuestionCircleOutlined />}>{row.author_name[0] || "G"}</Avatar>
                <div className="table-primary">
                  {row.user_id && hasPermission("customers.read")
                    ? <Link to={`/customers/${row.user_id}`}><strong>{row.author_name}</strong></Link>
                    : <strong>{row.author_name}</strong>}
                  <small>{row.author_email || copy.guest}</small>
                </div>
              </Space>
            ),
          },
          {
            title: copy.product,
            dataIndex: "product_name",
            key: "product",
            render: (value: string, row) => hasPermission("catalog.read")
              ? <Link to={`/catalog/products?product_id=${row.product_id}`}>{value}</Link>
              : value,
          },
          { title: copy.question, dataIndex: "text", key: "question", ellipsis: true, width: "34%" },
          {
            title: copy.status,
            dataIndex: "status",
            key: "status",
            render: (value: QuestionStatus) => (
              <Tag color={statusColor(value)}>
                {value === "published" ? copy.published : value === "rejected" ? copy.rejected : copy.pending}
              </Tag>
            ),
          },
          {
            title: copy.date,
            dataIndex: "created_at",
            key: "date",
            render: (value: string) => dateTime(value, locale),
          },
          {
            title: "",
            key: "action",
            align: "right",
            render: (_value, row) => (
              <Button icon={<EyeOutlined />} onClick={() => setSelected(row)}>
                {copy.inspect}
              </Button>
            ),
          },
        ]}
      />
      <Drawer
        width={640}
        open={Boolean(selected)}
        title={copy.moderation}
        onClose={() => setSelected(null)}
      >
        {selected ? (
          <Space direction="vertical" size={18} style={{ width: "100%" }}>
            <Descriptions size="small" column={1} bordered>
              <Descriptions.Item label={copy.author}>{selected.author_name}</Descriptions.Item>
              <Descriptions.Item label={copy.product}>{selected.product_name}</Descriptions.Item>
              <Descriptions.Item label={copy.date}>{dateTime(selected.created_at, locale)}</Descriptions.Item>
            </Descriptions>
            <Typography.Paragraph className="review-full-text">{selected.text}</Typography.Paragraph>
            <div>
              <Typography.Text strong>{copy.answer}</Typography.Text>
              <Input.TextArea
                value={answer}
                maxLength={4000}
                rows={5}
                onChange={(event) => setAnswer(event.target.value)}
              />
            </div>
            <div>
              <Typography.Text strong>{copy.internal}</Typography.Text>
              <Input.TextArea
                value={internalComment}
                maxLength={4000}
                rows={3}
                onChange={(event) => setInternalComment(event.target.value)}
              />
            </div>
            {hasPermission("reviews.moderate") ? (
              <Space>
                <Button
                  type="primary"
                  icon={<CheckOutlined />}
                  loading={moderate.isPending}
                  onClick={() => moderate.mutate("publish")}
                >
                  {copy.publish}
                </Button>
                <Button
                  danger
                  icon={<CloseOutlined />}
                  loading={moderate.isPending}
                  onClick={() => moderate.mutate("reject")}
                >
                  {copy.reject}
                </Button>
              </Space>
            ) : null}
          </Space>
        ) : null}
      </Drawer>
    </div>
  )
}
