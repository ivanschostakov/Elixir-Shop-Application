import { Spin } from "antd"
import type { ReactNode } from "react"
import { Navigate, useLocation } from "react-router-dom"
import { useAuth } from "./AuthProvider"

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { principal, booting } = useAuth()
  const location = useLocation()
  if (booting) return <div className="full-page-spin"><Spin size="large" /></div>
  if (!principal) return <Navigate to="/login" replace state={{ from: `${location.pathname}${location.search}` }} />
  return children
}
