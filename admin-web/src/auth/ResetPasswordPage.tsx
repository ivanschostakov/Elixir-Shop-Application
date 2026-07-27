import { LockOutlined, SafetyCertificateOutlined } from "@ant-design/icons"
import { Alert, Button, Card, Form, Input, Segmented, Typography } from "antd"
import { useMemo, useState } from "react"
import { Link, Navigate } from "react-router-dom"
import { apiRequest, ApiError } from "../api/client"
import { useLanguage } from "../i18n/LanguageProvider"
import { useAuth } from "./AuthProvider"

type ResetForm = {
  password: string
  passwordConfirm: string
}

export function ResetPasswordPage() {
  const { principal } = useAuth()
  const { locale, setLocale } = useLanguage()
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const token = useMemo(() => new URLSearchParams(window.location.hash.slice(1)).get("token") || "", [])

  if (principal) return <Navigate to="/" replace />

  const copy = locale === "ru"
    ? {
        eyebrow: "Безопасный доступ",
        title: "Новый пароль",
        subtitle: "Задайте новый пароль для Elixir Shop Admin",
        password: "Новый пароль",
        confirm: "Повторите пароль",
        submit: "Изменить пароль",
        invalid: "Ссылка восстановления повреждена или уже недействительна.",
        mismatch: "Пароли не совпадают",
        success: "Пароль изменён. Теперь можно войти с новым паролем.",
        login: "Перейти ко входу",
        failed: "Не удалось изменить пароль",
      }
    : {
        eyebrow: "Secure access",
        title: "New password",
        subtitle: "Set a new password for Elixir Shop Admin",
        password: "New password",
        confirm: "Repeat password",
        submit: "Change password",
        invalid: "The password reset link is damaged or no longer valid.",
        mismatch: "Passwords do not match",
        success: "Password changed. You can now sign in with the new password.",
        login: "Go to sign in",
        failed: "Could not change password",
      }

  const submit = async (values: ResetForm) => {
    if (!token) return
    setBusy(true)
    setError(null)
    try {
      await apiRequest("/auth/password-reset/confirm", {
        method: "POST",
        body: JSON.stringify({ token, password: values.password }),
      })
      setDone(true)
      window.history.replaceState(null, "", "/reset-password")
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : copy.failed)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="login-page">
      <div className="login-language">
        <Segmented value={locale} options={[{ label: "RU", value: "ru" }, { label: "EN", value: "en" }]} onChange={(value) => setLocale(value as "ru" | "en")} />
      </div>
      <section className="login-brand">
        <div className="brand-mark">E</div>
        <Typography.Text className="login-eyebrow">{copy.eyebrow}</Typography.Text>
        <Typography.Title>Elixir Shop</Typography.Title>
        <Typography.Paragraph>{copy.subtitle}</Typography.Paragraph>
        <div className="login-trust-row"><SafetyCertificateOutlined /> MFA · RBAC · Audit</div>
      </section>
      <Card className="login-card" bordered={false}>
        <Typography.Title level={2}>{copy.title}</Typography.Title>
        {!token ? <Alert type="error" message={copy.invalid} showIcon /> : null}
        {error ? <Alert type="error" message={error} showIcon closable onClose={() => setError(null)} /> : null}
        {done ? (
          <>
            <Alert type="success" message={copy.success} showIcon />
            <Link to="/login"><Button type="primary" block size="large" style={{ marginTop: 20 }}>{copy.login}</Button></Link>
          </>
        ) : (
          <Form layout="vertical" requiredMark={false} onFinish={submit} size="large" disabled={!token}>
            <Form.Item name="password" label={copy.password} rules={[{ required: true, min: 12 }]}>
              <Input.Password prefix={<LockOutlined />} autoComplete="new-password" />
            </Form.Item>
            <Form.Item
              name="passwordConfirm"
              label={copy.confirm}
              dependencies={["password"]}
              rules={[
                { required: true },
                ({ getFieldValue }) => ({
                  validator(_, value) {
                    return !value || getFieldValue("password") === value
                      ? Promise.resolve()
                      : Promise.reject(new Error(copy.mismatch))
                  },
                }),
              ]}
            >
              <Input.Password prefix={<LockOutlined />} autoComplete="new-password" />
            </Form.Item>
            <Button type="primary" htmlType="submit" block loading={busy}>{copy.submit}</Button>
          </Form>
        )}
      </Card>
    </main>
  )
}
