import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { afterEach, describe, expect, it } from "vitest"
import { LinkedCard } from "./LinkedCard"

afterEach(cleanup)

describe("LinkedCard", () => {
  it("uses a native internal link when a destination is available", () => {
    render(
      <MemoryRouter>
        <LinkedCard to="/analytics?tab=sales" linkLabel="Revenue">
          <span>120 ₽</span>
        </LinkedCard>
      </MemoryRouter>,
    )

    expect(screen.getByRole("link", { name: "Revenue" })).toHaveAttribute("href", "/analytics?tab=sales")
  })

  it("stays a regular card when access to a destination is unavailable", () => {
    render(
      <MemoryRouter>
        <LinkedCard>
          <span>120 ₽</span>
        </LinkedCard>
      </MemoryRouter>,
    )

    expect(screen.queryByRole("link")).not.toBeInTheDocument()
    expect(screen.getByText("120 ₽")).toBeInTheDocument()
  })
})
