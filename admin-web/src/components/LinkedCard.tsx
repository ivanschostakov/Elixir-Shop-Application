import { Card, type CardProps } from "antd"
import type { PropsWithChildren } from "react"
import { Link, type To } from "react-router-dom"

type LinkedCardProps = PropsWithChildren<CardProps & {
  to?: To
  linkLabel?: string
}>

export function LinkedCard({ to, linkLabel, className, children, ...cardProps }: LinkedCardProps) {
  const card = (
    <Card
      {...cardProps}
      className={[className, to ? "linked-card-panel" : ""].filter(Boolean).join(" ")}
    >
      {children}
    </Card>
  )

  return to ? (
    <Link className="linked-card" to={to} aria-label={linkLabel}>
      {card}
    </Link>
  ) : card
}
