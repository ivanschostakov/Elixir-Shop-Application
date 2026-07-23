import { describe, expect, it } from "vitest"
import { analyticsCsvPath } from "./AnalyticsPage"
import { campaignPayload, segmentFilters } from "./MarketingPage"

describe("segmentFilters", () => {
  it("builds a versioned visual segment definition", () => {
    expect(segmentFilters({
      name: "VIP",
      is_shared: true,
      segment_type: "dynamic",
      combinator: "and",
      conditions: [{ field: "order_count", operator: "gte", value: 3 }],
      exclusions: [],
    })).toEqual({
      version: 2,
      combinator: "and",
      conditions: [{ field: "order_count", operator: "gte", value: 3 }],
      exclusions: [],
    })
  })
})

describe("campaignPayload", () => {
  it("normalizes campaign text, template and UTM fields", () => {
    expect(campaignPayload({
      name: "  Winback ",
      title: " Hi ",
      body: " Come back ",
      deep_link: " /catalog ",
      segment_id: 7,
      template_id: 3,
      goal: " retention ",
      utm_source: " admin ",
      utm_campaign: " winback ",
      utm_content: "",
    })).toEqual({
      name: "Winback",
      title: "Hi",
      body: "Come back",
      deep_link: "/catalog",
      segment_id: 7,
      template_id: 3,
      goal: "retention",
      utm_json: { source: "admin", campaign: "winback" },
    })
  })
})

describe("analyticsCsvPath", () => {
  it("builds scoped analytics export paths", () => {
    expect(analyticsCsvPath("marketing", 90)).toBe("/analytics/marketing.csv?days=90")
  })
})
