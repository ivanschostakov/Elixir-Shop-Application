import { Alert, Button, Empty, Skeleton } from "antd"
import { useLanguage } from "../i18n/LanguageProvider"

export function QueryState({ loading, error, empty, onRetry }: { loading: boolean; error: boolean; empty?: boolean; onRetry?: () => void }) {
  const { t } = useLanguage()
  if (loading) return <Skeleton active paragraph={{ rows: 7 }} />
  if (error) return <Alert type="error" showIcon message={t("error")} action={onRetry ? <Button size="small" onClick={onRetry}>{t("retry")}</Button> : undefined} />
  if (empty) return <Empty description={t("noData")} image={Empty.PRESENTED_IMAGE_SIMPLE} />
  return null
}
