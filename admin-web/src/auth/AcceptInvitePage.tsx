import { CheckCircleOutlined, LockOutlined, SafetyCertificateOutlined, UserOutlined } from "@ant-design/icons"
import { Alert, Button, Card, Form, Input, Result, Segmented, Space, Spin, Tag, Typography } from "antd"
import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { apiRequest, ApiError } from "../api/client"
import type { AdminInvitationPreview } from "../api/types"
import { useLanguage } from "../i18n/LanguageProvider"
import { dateTime } from "../utils/format"

type AcceptValues = {
  name?: string
  surname?: string
  password: string
}

export function AcceptInvitePage() {
  const { locale, setLocale } = useLanguage()
  const [preview, setPreview] = useState<AdminInvitationPreview | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [accepted, setAccepted] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const token = useMemo(() => new URLSearchParams(window.location.hash.replace(/^#/, "")).get("token") || "", [])

  const copy = locale === "ru"
    ? {
        eyebrow: "Безопасное приглашение",
        title: "Присоединиться к Elixir Shop Admin",
        invitedBy: "Пригласил",
        roles: "Назначенные роли",
        expires: "Ссылка действует до",
        name: "Имя",
        surname: "Фамилия",
        password: "Новый пароль",
        existingPassword: "Пароль от вашего аккаунта Elixir Shop",
        existingHint: "Для этого email уже есть аккаунт покупателя. Подтвердите владение им текущим паролем.",
        newHint: "Создайте рабочий аккаунт. Email уже подтвержден одноразовой ссылкой.",
        accept: "Принять приглашение",
        invalid: "Ссылка приглашения отсутствует или повреждена.",
        unavailable: "Приглашение больше недоступно",
        acceptedTitle: "Доступ создан",
        acceptedText: "Теперь войдите в админку. При первом входе система попросит настроить MFA.",
        login: "Перейти ко входу",
      }
    : {
        eyebrow: "Secure invitation",
        title: "Join Elixir Shop Admin",
        invitedBy: "Invited by",
        roles: "Assigned roles",
        expires: "Link expires",
        name: "First name",
        surname: "Last name",
        password: "New password",
        existingPassword: "Your existing Elixir Shop password",
        existingHint: "A customer account already uses this email. Confirm ownership with its current password.",
        newHint: "Create your work account. The one-time link has already verified the email.",
        accept: "Accept invitation",
        invalid: "The invitation link is missing or malformed.",
        unavailable: "Invitation is no longer available",
        acceptedTitle: "Access created",
        acceptedText: "You can now sign in. MFA setup is required on the first login.",
        login: "Go to sign in",
      }

  useEffect(() => {
    if (!token) {
      setError(copy.invalid)
      setLoading(false)
      return
    }
    setLoading(true)
    apiRequest<AdminInvitationPreview>("/auth/invitations/preview", {
      method: "POST",
      body: JSON.stringify({ token }),
    })
      .then((result) => {
        setPreview(result)
        if (result.status !== "pending") setError(copy.unavailable)
      })
      .catch((requestError) => setError(requestError instanceof ApiError ? requestError.message : copy.unavailable))
      .finally(() => setLoading(false))
  }, [copy.invalid, copy.unavailable, token])

  const submit = async (values: AcceptValues) => {
    setSubmitting(true)
    setError(null)
    try {
      await apiRequest("/auth/invitations/accept", {
        method: "POST",
        body: JSON.stringify({ token, ...values }),
      })
      window.history.replaceState(null, "", "/accept-invite")
      setAccepted(true)
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : copy.unavailable)
    } finally {
      setSubmitting(false)
    }
  }

  if (accepted) {
    return (
      <main className="invite-page">
        <Card className="invite-card" bordered={false}>
          <Result
            status="success"
            icon={<CheckCircleOutlined />}
            title={copy.acceptedTitle}
            subTitle={copy.acceptedText}
            extra={<Link to={`/login?email=${encodeURIComponent(preview?.email || "")}`}><Button type="primary">{copy.login}</Button></Link>}
          />
        </Card>
      </main>
    )
  }

  return (
    <main className="invite-page">
      <div className="login-language">
        <Segmented value={locale} options={[{ label: "RU", value: "ru" }, { label: "EN", value: "en" }]} onChange={(value) => setLocale(value as "ru" | "en")} />
      </div>
      <Card className="invite-card" bordered={false}>
        <Space direction="vertical" size={18} style={{ width: "100%" }}>
          <div className="brand-mark brand-mark-small">E</div>
          <div>
            <Typography.Text className="login-eyebrow">{copy.eyebrow}</Typography.Text>
            <Typography.Title level={2}>{copy.title}</Typography.Title>
          </div>
          {loading ? <Spin /> : null}
          {error ? <Alert type="error" showIcon message={error} /> : null}
          {preview ? (
            <>
              <div className="invite-summary">
                <div><Typography.Text type="secondary">{copy.invitedBy}</Typography.Text><strong>{preview.invited_by_name}</strong></div>
                <div><Typography.Text type="secondary">{copy.roles}</Typography.Text><Space wrap>{(locale === "ru" ? preview.role_names_ru : preview.role_names_en).map((name) => <Tag color="cyan" key={name}>{name}</Tag>)}</Space></div>
                <div><Typography.Text type="secondary">{copy.expires}</Typography.Text><strong>{dateTime(preview.expires_at, locale)}</strong></div>
              </div>
              {preview.status === "pending" ? (
                <Form layout="vertical" size="large" requiredMark={false} onFinish={submit}>
                  <Alert type="info" showIcon icon={preview.existing_user ? <SafetyCertificateOutlined /> : <UserOutlined />} message={preview.existing_user ? copy.existingHint : copy.newHint} />
                  {!preview.existing_user ? (
                    <div className="invite-name-grid">
                      <Form.Item name="name" label={copy.name} rules={[{ required: true, min: 1, max: 120 }]}><Input autoComplete="given-name" /></Form.Item>
                      <Form.Item name="surname" label={copy.surname} rules={[{ required: true, min: 1, max: 120 }]}><Input autoComplete="family-name" /></Form.Item>
                    </div>
                  ) : null}
                  <Form.Item name="password" label={preview.existing_user ? copy.existingPassword : copy.password} rules={[{ required: true, min: 8, max: 128 }]}>
                    <Input.Password prefix={<LockOutlined />} autoComplete={preview.existing_user ? "current-password" : "new-password"} />
                  </Form.Item>
                  <Button type="primary" htmlType="submit" block loading={submitting}>{copy.accept}</Button>
                </Form>
              ) : null}
            </>
          ) : null}
        </Space>
      </Card>
    </main>
  )
}
