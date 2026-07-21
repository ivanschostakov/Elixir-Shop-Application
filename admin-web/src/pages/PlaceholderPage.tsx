import { ClockCircleOutlined } from "@ant-design/icons"
import { Card, Result } from "antd"
import { PageHeader } from "../components/PageHeader"
import { useLanguage } from "../i18n/LanguageProvider"

export function PlaceholderPage({ section }: { section: "communications" | "analytics" }) {
  const { locale } = useLanguage()
  const title = section === "communications" ? (locale === "ru" ? "Коммуникации" : "Communications") : locale === "ru" ? "Аналитика" : "Analytics"
  const description = section === "communications"
    ? locale === "ru" ? "Telegram-сообщество и AI-чаты будут подключены в следующем этапе CRM." : "Telegram community and AI chats will arrive in the next CRM phase."
    : locale === "ru" ? "Базовые показатели уже доступны на главной; расширенные отчёты готовятся." : "Core metrics are already on the dashboard; advanced reports are in progress."
  return <div className="page-stack"><PageHeader title={title} /><Card><Result icon={<ClockCircleOutlined />} title={title} subTitle={description} /></Card></div>
}
