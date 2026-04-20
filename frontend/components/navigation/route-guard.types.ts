import type { ReactNode } from "react"
import type { Href } from "expo-router"

export type RouteGuardProps = {
    children: ReactNode
    redirectTo?: Href
}
