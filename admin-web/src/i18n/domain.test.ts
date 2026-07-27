import { describe, expect, it } from "vitest"
import { domainLabel, humanizeApiError } from "./domain"


describe("domainLabel", () => {
  it("localizes registered system values", () => {
    expect(domainLabel("waiting_customer", "ru")).toBe("Ожидаем клиента")
    expect(domainLabel("website_reviews", "en")).toBe("Website reviews")
  })

  it("preserves unknown values exactly", () => {
    expect(domainLabel("Some_NEW_value", "ru")).toBe("Some_NEW_value")
    expect(domainLabel("custom.snake_CASE", "en")).toBe("custom.snake_CASE")
    expect(domainLabel("  unknown_raw_value  ", "ru")).toBe("  unknown_raw_value  ")
    expect(domainLabel("", "ru")).toBe("")
  })
})

describe("humanizeApiError", () => {
  it("uses a human-readable localized message", () => {
    expect(humanizeApiError("Invalid email or password", 401, "ru")).toBe("Неверный email или пароль")
    expect(humanizeApiError("opaque_upstream_trace", 503, "en")).toBe("opaque_upstream_trace")
  })
})
