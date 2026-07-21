import { ConfigProvider, Result, Spin, theme } from "antd"
import enUS from "antd/locale/en_US"
import ruRU from "antd/locale/ru_RU"
import { lazy, Suspense, type ReactNode } from "react"
import { Navigate, Route, Routes } from "react-router-dom"
import { PermissionRoute } from "./auth/PermissionRoute"
import { ProtectedRoute } from "./auth/ProtectedRoute"
import { LoginPage } from "./auth/LoginPage"
import { useLanguage } from "./i18n/LanguageProvider"
import { AdminLayout } from "./layout/AdminLayout"
const DashboardPage = lazy(() => import("./pages/DashboardPage").then((module) => ({ default: module.DashboardPage })))
const IntegrationsPage = lazy(() => import("./pages/IntegrationsPage").then((module) => ({ default: module.IntegrationsPage })))
const MarketingPage = lazy(() => import("./pages/MarketingPage").then((module) => ({ default: module.MarketingPage })))
const PlaceholderPage = lazy(() => import("./pages/PlaceholderPage").then((module) => ({ default: module.PlaceholderPage })))
const CategoriesPage = lazy(() => import("./pages/catalog/CategoriesPage").then((module) => ({ default: module.CategoriesPage })))
const ProductsPage = lazy(() => import("./pages/catalog/ProductsPage").then((module) => ({ default: module.ProductsPage })))
const BannersPage = lazy(() => import("./pages/content/BannersPage").then((module) => ({ default: module.BannersPage })))
const ReviewsPage = lazy(() => import("./pages/content/ReviewsPage").then((module) => ({ default: module.ReviewsPage })))
const CustomerDetailPage = lazy(() => import("./pages/customers/CustomerDetailPage").then((module) => ({ default: module.CustomerDetailPage })))
const CustomersPage = lazy(() => import("./pages/customers/CustomersPage").then((module) => ({ default: module.CustomersPage })))
const OrderDetailPage = lazy(() => import("./pages/orders/OrderDetailPage").then((module) => ({ default: module.OrderDetailPage })))
const OrdersPage = lazy(() => import("./pages/orders/OrdersPage").then((module) => ({ default: module.OrdersPage })))
const AuditPage = lazy(() => import("./pages/settings/AuditPage").then((module) => ({ default: module.AuditPage })))
const StaffPage = lazy(() => import("./pages/settings/StaffPage").then((module) => ({ default: module.StaffPage })))

const guarded = (permission: string, node: ReactNode) => <PermissionRoute permission={permission}>{node}</PermissionRoute>

export default function App() {
  const { locale } = useLanguage()
  return (
    <ConfigProvider
      locale={locale === "ru" ? ruRU : enUS}
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: "#0f766e",
          colorInfo: "#2563eb",
          borderRadius: 10,
          fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
          colorBgLayout: "#f4f6f8",
          colorText: "#172033",
        },
        components: {
          Layout: { headerBg: "#ffffff", siderBg: "#ffffff" },
          Menu: { itemBorderRadius: 8, itemMarginInline: 10, itemSelectedBg: "#e8f5f2", itemSelectedColor: "#0f766e" },
          Table: { headerBg: "#f8fafb", headerColor: "#657083" },
          Card: { headerFontSize: 15 },
        },
      }}
    >
      <Suspense fallback={<div className="full-page-spin"><Spin size="large" /></div>}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute><AdminLayout /></ProtectedRoute>}>
          <Route index element={guarded("dashboard.read", <DashboardPage />)} />
          <Route path="sales/orders" element={guarded("orders.read", <OrdersPage />)} />
          <Route path="sales/orders/:orderId" element={guarded("orders.read", <OrderDetailPage />)} />
          <Route path="customers" element={guarded("customers.read", <CustomersPage />)} />
          <Route path="customers/:customerId" element={guarded("customers.read", <CustomerDetailPage />)} />
          <Route path="catalog/products" element={guarded("catalog.read", <ProductsPage />)} />
          <Route path="catalog/categories" element={guarded("catalog.read", <CategoriesPage />)} />
          <Route path="content/reviews" element={guarded("reviews.read", <ReviewsPage />)} />
          <Route path="content/banners" element={guarded("banners.manage", <BannersPage />)} />
          <Route path="marketing" element={guarded("referrals.read", <MarketingPage />)} />
          <Route path="communications" element={guarded("community.read", <PlaceholderPage section="communications" />)} />
          <Route path="analytics" element={guarded("analytics.read", <PlaceholderPage section="analytics" />)} />
          <Route path="integrations" element={guarded("integrations.read", <IntegrationsPage />)} />
          <Route path="settings/staff" element={guarded("staff.manage", <StaffPage />)} />
          <Route path="settings/audit" element={guarded("audit.read", <AuditPage />)} />
          <Route path="404" element={<Result status="404" title="404" subTitle="Page not found" />} />
          <Route path="*" element={<Navigate to="/404" replace />} />
        </Route>
      </Routes>
      </Suspense>
    </ConfigProvider>
  )
}
