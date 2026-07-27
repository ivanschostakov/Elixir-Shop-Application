import { describe, expect, it } from "vitest"
import { INTERNAL_APP_LINK_GUIDE, internalAppLinkError } from "./internalLinks"

describe("internal app links", () => {
  it("documents only paths accepted by the shared validator", () => {
    for (const entry of INTERNAL_APP_LINK_GUIDE) {
      expect(internalAppLinkError(entry.example, "ru"), entry.example).toBeNull()
    }
  })

  it("accepts supported parameters and numeric product IDs", () => {
    expect(internalAppLinkError("/discover?tab=products&q=ghk-cu&categoryId=12", "ru")).toBeNull()
    expect(internalAppLinkError("/chat?mode=support&conversationId=42", "ru")).toBeNull()
    expect(internalAppLinkError("/products/123", "ru")).toBeNull()
  })

  it("rejects external, unknown and malformed product paths", () => {
    expect(internalAppLinkError("https://example.com", "ru")).toContain("/")
    expect(internalAppLinkError("/catalog/products", "ru")).toContain("нет")
    expect(internalAppLinkError("/products/abc", "ru")).toContain("числовой ID")
  })
})
