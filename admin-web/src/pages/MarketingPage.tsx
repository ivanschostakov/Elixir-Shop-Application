import { useQuery } from "@tanstack/react-query"
import { Card, Col, Row, Statistic, Table, Tag } from "antd"
import { apiRequest } from "../api/client"
import type { ReferralProfile } from "../api/types"
import { PageHeader } from "../components/PageHeader"
import { useLanguage } from "../i18n/LanguageProvider"
import { dateTime, money } from "../utils/format"

export function MarketingPage() {
  const { locale } = useLanguage()
  const query = useQuery({ queryKey: ["referrals"], queryFn: () => apiRequest<ReferralProfile[]>("/referrals/profiles?limit=100&offset=0") })
  const rows = query.data || []
  const copy = locale === "ru" ? { title: "Маркетинг", description: "Реферальная программа и персональные скидки", profiles: "Участники", base: "База скидки", discount: "Текущая скидка", purchases: "Покупки", created: "Создан" } : { title: "Marketing", description: "Referral program and personal discounts", profiles: "Members", base: "Discount base", discount: "Current discount", purchases: "Purchases", created: "Created" }
  return <div className="page-stack"><PageHeader title={copy.title} description={copy.description} /><Row gutter={[16, 16]}><Col xs={24} md={8}><Card><Statistic title={copy.profiles} value={rows.length} /></Card></Col><Col xs={24} md={8}><Card><Statistic title={copy.base} value={money(rows.reduce((sum, row) => sum + Number(row.referral_discount_base_total), 0), "RUB", locale)} /></Card></Col><Col xs={24} md={8}><Card><Statistic title={copy.purchases} value={money(rows.reduce((sum, row) => sum + Number(row.total_purchases), 0), "RUB", locale)} /></Card></Col></Row><Table<ReferralProfile> rowKey="id" loading={query.isLoading} dataSource={rows} pagination={{ pageSize: 25 }} columns={[{ title: "User ID", dataIndex: "user_id" }, { title: copy.purchases, dataIndex: "total_purchases", render: (value: string) => money(value, "RUB", locale) }, { title: copy.base, dataIndex: "referral_discount_base_total", render: (value: string) => money(value, "RUB", locale) }, { title: copy.discount, dataIndex: "current_discount_percent", render: (value: string) => <Tag color="green">{value}%</Tag> }, { title: copy.created, dataIndex: "created_at", render: (value: string) => dateTime(value, locale) }]} /></div>
}
