import { describe, expect, it } from "vitest"
import { money, statusLabel } from "./format"

describe("localized formatting", () => {
  it("provides Russian and English order status labels", () => {
    expect(statusLabel("waiting_response", "ru")).toBe("Ожидание ответа")
    expect(statusLabel("waiting_response", "en")).toBe("Waiting for response")
  })

  it("formats RUB for both interface locales", () => {
    expect(money(1250, "RUB", "ru")).toContain("1 250")
    expect(money(1250, "RUB", "en")).toContain("1,250")
  })
})
