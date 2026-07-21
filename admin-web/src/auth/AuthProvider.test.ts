import { describe, expect, it } from "vitest"
import type { AdminPrincipal } from "../api/types"
import { principalHasPermission } from "./AuthProvider"

function principal(permissions: string[]): AdminPrincipal {
  return {
    user: { id: 1, email: "admin@example.com", name: "Admin", surname: "User", locale: "ru" },
    roles: ["content"],
    permissions,
  }
}

describe("principalHasPermission", () => {
  it("allows an explicitly assigned permission", () => {
    expect(principalHasPermission(principal(["reviews.read"]), "reviews.read")).toBe(true)
  })

  it("denies missing permissions and anonymous users", () => {
    expect(principalHasPermission(principal(["reviews.read"]), "reviews.moderate")).toBe(false)
    expect(principalHasPermission(null, "reviews.read")).toBe(false)
  })

  it("allows all permissions for superadmins", () => {
    expect(principalHasPermission(principal(["*"]), "integrations.retry")).toBe(true)
  })
})
