import { Typography } from "antd"
import type { ReactNode } from "react"

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return (
    <header className="page-header">
      <div>
        <Typography.Title level={2}>{title}</Typography.Title>
        {description ? <Typography.Paragraph type="secondary">{description}</Typography.Paragraph> : null}
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </header>
  )
}
