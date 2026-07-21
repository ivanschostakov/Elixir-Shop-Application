import { LockOutlined, MailOutlined, SafetyCertificateOutlined } from "@ant-design/icons"
import { Alert, Button, Card, Form, Input, Segmented, Space, Spin, Typography } from "antd"
import { useState } from "react"
import { QRCodeSVG } from "qrcode.react"
import { Navigate, useLocation, useNavigate } from "react-router-dom"
import { apiRequest, ApiError } from "../api/client"
import type { AdminAuthResponse, AdminChallenge } from "../api/types"
import { useLanguage } from "../i18n/LanguageProvider"
import { useAuth } from "./AuthProvider"

type SetupDetails = { secret: string; otpauth_uri: string }

export function LoginPage() {
  const { principal, login, acceptAuth } = useAuth()
  const { locale, setLocale } = useLanguage()
  const navigate = useNavigate()
  const location = useLocation()
  const [challenge, setChallenge] = useState<AdminChallenge | null>(null)
  const [setup, setSetup] = useState<SetupDetails | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const from = (location.state as { from?: string } | null)?.from || "/"

  if (principal) return <Navigate to={from} replace />

  const submitCredentials = async (values: { email: string; password: string }) => {
    setBusy(true)
    setError(null)
    try {
      const next = await login(values.email, values.password)
      setChallenge(next)
      if (next.status === "mfa_setup_required") {
        const details = await apiRequest<SetupDetails>("/auth/mfa/setup", {
          method: "POST",
          body: JSON.stringify({ challenge_token: next.challenge_token }),
        })
        setSetup(details)
      }
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : locale === "ru" ? "Не удалось войти" : "Sign in failed")
    } finally {
      setBusy(false)
    }
  }

  const submitCode = async (values: { code: string }) => {
    if (!challenge) return
    setBusy(true)
    setError(null)
    try {
      const path = challenge.status === "mfa_setup_required" ? "/auth/mfa/confirm" : "/auth/mfa/verify"
      const auth = await apiRequest<AdminAuthResponse>(path, {
        method: "POST",
        body: JSON.stringify({ challenge_token: challenge.challenge_token, code: values.code }),
      })
      acceptAuth(auth)
      navigate(from, { replace: true })
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : locale === "ru" ? "Неверный код" : "Invalid code")
    } finally {
      setBusy(false)
    }
  }

  const copy = locale === "ru"
    ? {
        eyebrow: "Внутренняя система",
        title: "Elixir Shop",
        subtitle: "Панель управления продажами и магазином",
        email: "Рабочий email",
        password: "Пароль",
        signIn: "Продолжить",
        code: "Код из приложения",
        verify: "Подтвердить вход",
        setupTitle: "Настройте двухфакторную защиту",
        setupText: "Отсканируйте код в приложении-аутентификаторе, затем введите одноразовый код.",
        codeTitle: "Подтвердите вход",
        codeText: "Введите шестизначный код из приложения-аутентификатора.",
        back: "Вернуться",
      }
    : {
        eyebrow: "Internal workspace",
        title: "Elixir Shop",
        subtitle: "Sales and store operations",
        email: "Work email",
        password: "Password",
        signIn: "Continue",
        code: "Authenticator code",
        verify: "Verify sign in",
        setupTitle: "Set up two-factor protection",
        setupText: "Scan the code in your authenticator app, then enter the one-time code.",
        codeTitle: "Verify your sign in",
        codeText: "Enter the six-digit code from your authenticator app.",
        back: "Go back",
      }

  return (
    <main className="login-page">
      <div className="login-language">
        <Segmented value={locale} options={[{ label: "RU", value: "ru" }, { label: "EN", value: "en" }]} onChange={(value) => setLocale(value as "ru" | "en")} />
      </div>
      <section className="login-brand">
        <div className="brand-mark">E</div>
        <Typography.Text className="login-eyebrow">{copy.eyebrow}</Typography.Text>
        <Typography.Title>{copy.title}</Typography.Title>
        <Typography.Paragraph>{copy.subtitle}</Typography.Paragraph>
        <div className="login-trust-row"><SafetyCertificateOutlined /> MFA · RBAC · Audit</div>
      </section>
      <Card className="login-card" bordered={false}>
        {error ? <Alert type="error" message={error} showIcon closable onClose={() => setError(null)} /> : null}
        {!challenge ? (
          <Form layout="vertical" requiredMark={false} onFinish={submitCredentials} size="large">
            <Form.Item name="email" label={copy.email} rules={[{ required: true }, { type: "email" }]}>
              <Input prefix={<MailOutlined />} autoComplete="username" placeholder="name@company.ru" />
            </Form.Item>
            <Form.Item name="password" label={copy.password} rules={[{ required: true, min: 8 }]}>
              <Input.Password prefix={<LockOutlined />} autoComplete="current-password" />
            </Form.Item>
            <Button type="primary" htmlType="submit" block loading={busy}>{copy.signIn}</Button>
          </Form>
        ) : (
          <Space direction="vertical" size={20} style={{ width: "100%" }}>
            <div>
              <Typography.Title level={3}>{challenge.status === "mfa_setup_required" ? copy.setupTitle : copy.codeTitle}</Typography.Title>
              <Typography.Paragraph type="secondary">{challenge.status === "mfa_setup_required" ? copy.setupText : copy.codeText}</Typography.Paragraph>
            </div>
            {challenge.status === "mfa_setup_required" ? (
              setup ? (
                <div className="mfa-setup">
                  <div className="qr-card"><QRCodeSVG value={setup.otpauth_uri} size={164} /></div>
                  <Typography.Text copyable={{ text: setup.secret }} code>{setup.secret}</Typography.Text>
                </div>
              ) : <Spin />
            ) : null}
            <Form layout="vertical" requiredMark={false} onFinish={submitCode} size="large">
              <Form.Item name="code" label={copy.code} rules={[{ required: true, len: 6, pattern: /^\d{6}$/ }]}>
                <Input.OTP length={6} autoFocus />
              </Form.Item>
              <Button type="primary" htmlType="submit" block loading={busy}>{copy.verify}</Button>
            </Form>
            <Button type="text" onClick={() => { setChallenge(null); setSetup(null); setError(null) }}>{copy.back}</Button>
          </Space>
        )}
      </Card>
    </main>
  )
}
