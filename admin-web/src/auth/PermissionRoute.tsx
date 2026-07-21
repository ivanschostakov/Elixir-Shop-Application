import { Result } from "antd"
import type { ReactNode } from "react"
import { useLanguage } from "../i18n/LanguageProvider"
import { useAuth } from "./AuthProvider"

export function PermissionRoute({ permission, children }: { permission: string; children: ReactNode }) {
  const { hasPermission } = useAuth()
  const { locale } = useLanguage()
  if (!hasPermission(permission)) return <Result status="403" title="403" subTitle={locale === "ru" ? "У вас нет доступа к этому разделу." : "You do not have permission to open this section."} />
  return children
}
