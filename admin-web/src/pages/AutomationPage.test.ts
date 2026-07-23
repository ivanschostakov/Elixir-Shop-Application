import { describe, expect, it } from "vitest"
import { automationRulePayload } from "./AutomationPage"

describe("automationRulePayload", () => {
  it("creates new rules disabled and keeps explicit order conditions", () => {
    const payload = automationRulePayload({
      name: "Paid without delivery",
      priority: 10,
      is_enabled: true,
      status_codes: ["paid"],
      payment_statuses: ["paid"],
      min_age_minutes: 30,
      missing_delivery: true,
      only_active: true,
      action_kind: "queue_operation",
      operation: "delivery_create",
    }, null)
    expect(payload.is_enabled).toBe(false)
    expect(payload.conditions_json).toMatchObject({ status_codes: ["paid"], missing_delivery: true })
    expect(payload.action_json).toEqual({ kind: "queue_operation", operation: "delivery_create" })
  })
})
