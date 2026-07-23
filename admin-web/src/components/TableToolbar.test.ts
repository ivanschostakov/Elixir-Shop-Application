import { describe, expect, it } from "vitest"
import { parseVisibleColumns } from "./TableToolbar"

describe("parseVisibleColumns", () => {
  const allowed = ["customer", "orders", "state"]

  it("uses every column when the URL has no valid selection", () => {
    expect(parseVisibleColumns(null, allowed)).toEqual(allowed)
    expect(parseVisibleColumns("unknown", allowed)).toEqual(allowed)
  })

  it("keeps only unique allowed columns", () => {
    expect(parseVisibleColumns("state,customer,state,secret", allowed)).toEqual(["state", "customer"])
  })
})
