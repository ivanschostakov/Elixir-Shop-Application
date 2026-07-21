import {
  ApiOutlined,
  AppstoreOutlined,
  AuditOutlined,
  BarChartOutlined,
  BellOutlined,
  CommentOutlined,
  DashboardOutlined,
  GiftOutlined,
  GlobalOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  ProductOutlined,
  SearchOutlined,
  SettingOutlined,
  ShoppingCartOutlined,
  TeamOutlined,
  UserOutlined,
} from "@ant-design/icons"
import { useQuery } from "@tanstack/react-query"
import { AutoComplete, Avatar, Badge, Button, Drawer, Dropdown, Empty, Input, Layout, List, Menu, Segmented, Space, Tag, Typography } from "antd"
import { useMemo, useState } from "react"
import { Outlet, useLocation, useNavigate } from "react-router-dom"
import { apiRequest, queryString } from "../api/client"
import type { Dashboard, SearchResult } from "../api/types"
import { useAuth } from "../auth/AuthProvider"
import { useLanguage } from "../i18n/LanguageProvider"

const { Header, Sider, Content } = Layout

export function AdminLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const [search, setSearch] = useState("")
  const [notificationCenterOpen, setNotificationCenterOpen] = useState(false)
  const { principal, logout, hasPermission } = useAuth()
  const { locale, setLocale, t } = useLanguage()
  const navigate = useNavigate()
  const location = useLocation()
  const { data: searchResults } = useQuery({
    queryKey: ["global-search", search],
    queryFn: () => apiRequest<{ items: SearchResult[] }>(`/search${queryString({ q: search.trim() })}`),
    enabled: search.trim().length >= 2,
    staleTime: 15_000,
  })
  const { data: dashboard } = useQuery({
    queryKey: ["dashboard", "notification-center"],
    queryFn: () => apiRequest<Dashboard>("/dashboard"),
    enabled: hasPermission("dashboard.read"),
    refetchInterval: 60_000,
  })

  const items = useMemo(() => {
    const allowed = (permission: string) => hasPermission(permission)
    return [
      allowed("dashboard.read") ? { key: "/", icon: <DashboardOutlined />, label: t("dashboard") } : null,
      allowed("orders.read") ? {
        key: "sales",
        icon: <ShoppingCartOutlined />,
        label: t("sales"),
        children: [{ key: "/sales/orders", label: t("orders") }],
      } : null,
      allowed("customers.read") ? { key: "/customers", icon: <TeamOutlined />, label: t("customers") } : null,
      allowed("catalog.read") ? {
        key: "catalog",
        icon: <ProductOutlined />,
        label: t("catalog"),
        children: [
          { key: "/catalog/products", label: t("products") },
          { key: "/catalog/categories", label: t("categories") },
        ],
      } : null,
      allowed("reviews.read") || allowed("banners.manage") ? {
        key: "content",
        icon: <CommentOutlined />,
        label: t("content"),
        children: [
          allowed("reviews.read") ? { key: "/content/reviews", label: t("reviews") } : null,
          allowed("banners.manage") ? { key: "/content/banners", label: t("banners") } : null,
        ].filter(Boolean),
      } : null,
      allowed("notifications.manage") || allowed("referrals.read") ? { key: "/marketing", icon: <GiftOutlined />, label: t("marketing") } : null,
      allowed("community.read") || allowed("ai_chats.read") ? { key: "/communications", icon: <GlobalOutlined />, label: t("communications") } : null,
      allowed("analytics.read") ? { key: "/analytics", icon: <BarChartOutlined />, label: t("analytics") } : null,
      allowed("integrations.read") ? { key: "/integrations", icon: <ApiOutlined />, label: t("integrations") } : null,
      allowed("staff.manage") || allowed("audit.read") ? {
        key: "settings",
        icon: <SettingOutlined />,
        label: t("settings"),
        children: [
          allowed("staff.manage") ? { key: "/settings/staff", icon: <UserOutlined />, label: t("staff") } : null,
          allowed("audit.read") ? { key: "/settings/audit", icon: <AuditOutlined />, label: t("audit") } : null,
        ].filter(Boolean),
      } : null,
    ].filter(Boolean)
  }, [hasPermission, t])

  const selectedKey = location.pathname === "/" ? "/" : `/${location.pathname.split("/").filter(Boolean).slice(0, 2).join("/")}`
  const initials = `${principal?.user.name?.[0] || ""}${principal?.user.surname?.[0] || ""}`.toUpperCase() || "A"
  const environment = import.meta.env.VITE_ENVIRONMENT || import.meta.env.MODE
  const notificationItems = dashboard ? [
    { key: "payments", count: dashboard.metrics.failed_payments, label: locale === "ru" ? "Проблемные оплаты" : "Payment issues", path: "/sales/orders" },
    { key: "reviews", count: dashboard.metrics.pending_reviews, label: locale === "ru" ? "Отзывы на модерации" : "Reviews awaiting moderation", path: "/content/reviews" },
    { key: "integrations", count: dashboard.metrics.integration_errors, label: locale === "ru" ? "Ошибки интеграций" : "Integration errors", path: "/integrations" },
    { key: "stock", count: dashboard.metrics.low_stock_variants, label: locale === "ru" ? "Низкие остатки" : "Low stock", path: "/catalog/products" },
  ].filter((item) => item.count > 0) : []
  const notificationCount = notificationItems.reduce((total, item) => total + item.count, 0)
  const searchOptions = (searchResults?.items || []).map((item) => ({
    value: item.path,
    label: (
      <div className="search-option">
        <div><strong>{item.title}</strong><span>{item.subtitle}</span></div>
        <Tag bordered={false}>{item.type}</Tag>
      </div>
    ),
  }))

  return (
    <Layout className="admin-shell">
      <Sider width={248} collapsedWidth={76} collapsed={collapsed} trigger={null} className="admin-sider">
        <div className="sidebar-brand">
          <div className="brand-mark brand-mark-small">E</div>
          {!collapsed ? <div><strong>Elixir Shop</strong><span>Admin</span></div> : null}
        </div>
        <Menu
          mode="inline"
          items={items}
          selectedKeys={[selectedKey]}
          defaultOpenKeys={["sales", "catalog", "content", "settings"]}
          onClick={({ key }) => key.startsWith("/") && navigate(key)}
        />
        <div className="sidebar-footer">
          {!collapsed ? <><span className="status-dot" /> <span>{t("environment")}: {environment}</span></> : <span className="status-dot" />}
        </div>
      </Sider>
      <Layout>
        <Header className="admin-header">
          <Button type="text" className="collapse-button" icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />} onClick={() => setCollapsed((value) => !value)} />
          <AutoComplete
            className="global-search"
            value={search}
            options={searchOptions}
            onChange={setSearch}
            onSelect={(path) => { navigate(path); setSearch("") }}
          >
            <Input prefix={<SearchOutlined />} placeholder={t("search")} allowClear />
          </AutoComplete>
          <Space size={12} className="header-actions">
            <Segmented
              size="small"
              value={locale}
              options={[{ label: "RU", value: "ru" }, { label: "EN", value: "en" }]}
              onChange={(value) => {
                const nextLocale = value as "ru" | "en"
                setLocale(nextLocale)
                void apiRequest("/auth/me/locale", { method: "PATCH", body: JSON.stringify({ locale: nextLocale }) }).catch(() => undefined)
              }}
            />
            <Badge count={notificationCount} overflowCount={99} size="small"><Button type="text" icon={<BellOutlined />} aria-label="Notifications" onClick={() => setNotificationCenterOpen(true)} /></Badge>
            <Dropdown
              trigger={["click"]}
              menu={{ items: [{ key: "logout", icon: <LogoutOutlined />, label: t("logout"), onClick: () => void logout() }] }}
            >
              <button className="profile-button">
                <Avatar>{initials}</Avatar>
                <span><Typography.Text strong>{principal?.user.name} {principal?.user.surname}</Typography.Text><Typography.Text type="secondary">{principal?.roles[0] || "admin"}</Typography.Text></span>
              </button>
            </Dropdown>
          </Space>
        </Header>
        <Content className="admin-content"><Outlet /></Content>
      </Layout>
      <Drawer
        title={locale === "ru" ? "Центр внимания" : "Attention center"}
        open={notificationCenterOpen}
        width={420}
        onClose={() => setNotificationCenterOpen(false)}
      >
        {notificationItems.length ? (
          <List
            dataSource={notificationItems}
            renderItem={(item) => (
              <List.Item actions={[<Button key="open" type="link" onClick={() => { navigate(item.path); setNotificationCenterOpen(false) }}>{t("open")}</Button>]}>
                <List.Item.Meta title={item.label} description={`${item.count}`} />
              </List.Item>
            )}
          />
        ) : <Empty description={locale === "ru" ? "Нет новых проблем" : "No new issues"} />}
      </Drawer>
    </Layout>
  )
}
