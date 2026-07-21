import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react"
import { apiRequest, refreshAdminSession, setAccessToken, setAuthListener } from "../api/client"
import type { AdminAuthResponse, AdminChallenge, AdminPrincipal } from "../api/types"

type AuthContextValue = {
  principal: AdminPrincipal | null
  booting: boolean
  acceptAuth: (auth: AdminAuthResponse) => void
  login: (email: string, password: string) => Promise<AdminChallenge>
  logout: () => Promise<void>
  hasPermission: (permission: string) => boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function principalHasPermission(principal: AdminPrincipal | null, permission: string) {
  return Boolean(principal?.permissions.includes("*") || principal?.permissions.includes(permission))
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [principal, setPrincipal] = useState<AdminPrincipal | null>(null)
  const [booting, setBooting] = useState(true)

  const acceptAuth = useCallback((auth: AdminAuthResponse) => {
    setAccessToken(auth.access_token)
    setPrincipal(auth.principal)
  }, [])

  useEffect(() => {
    setAuthListener((auth) => {
      if (auth) acceptAuth(auth)
      else setPrincipal(null)
    })
    void refreshAdminSession()
      .then(acceptAuth)
      .catch(() => {
        setAccessToken(null)
        setPrincipal(null)
      })
      .finally(() => setBooting(false))
    return () => setAuthListener(null)
  }, [acceptAuth])

  const login = useCallback(
    (email: string, password: string) =>
      apiRequest<AdminChallenge>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }),
    [],
  )

  const logout = useCallback(async () => {
    try {
      await apiRequest("/auth/logout", { method: "POST" })
    } finally {
      setAccessToken(null)
      setPrincipal(null)
    }
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      principal,
      booting,
      acceptAuth,
      login,
      logout,
      hasPermission: (permission) => principalHasPermission(principal, permission),
    }),
    [acceptAuth, booting, login, logout, principal],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error("useAuth must be used inside AuthProvider")
  return context
}
