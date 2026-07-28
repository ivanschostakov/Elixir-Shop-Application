import { describe, expect, it } from "vitest"
import { resolveAdminMediaUrl } from "./media"

describe("resolveAdminMediaUrl", () => {
  it("rewrites API media URLs to the admin origin", () => {
    expect(resolveAdminMediaUrl(
      "https://api.example.test/media/products/42/variant.png?v=123",
    )).toBe("/media/products/42/variant.png?v=123")
  })

  it("keeps same-origin media paths unchanged", () => {
    expect(resolveAdminMediaUrl("/media/banners/banner.png")).toBe("/media/banners/banner.png")
  })

  it("does not rewrite unrelated external URLs", () => {
    expect(resolveAdminMediaUrl("https://cdn.example.test/banner.png"))
      .toBe("https://cdn.example.test/banner.png")
  })

  it("returns undefined for an empty value", () => {
    expect(resolveAdminMediaUrl("  ")).toBeUndefined()
    expect(resolveAdminMediaUrl(null)).toBeUndefined()
  })
})
