import type { ReactNode } from "react"

import type { ProductRead } from "@/types/product"

export type ListCardProps = {
    product: ProductRead
    action?: ReactNode
    eyebrow?: string
}
