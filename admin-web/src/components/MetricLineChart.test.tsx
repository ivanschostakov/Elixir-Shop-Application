import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { MetricLineChart } from "./MetricLineChart"

const points = [
  { key: "one", label: "08-01", tooltipLabel: "1 августа", values: { revenue: 1000, orders: 2 } },
  { key: "two", label: "08-02", tooltipLabel: "2 августа", values: { revenue: 2500, orders: 4 } },
]

describe("MetricLineChart", () => {
  it("shows an explanation and exposes exact values with keyboard navigation", () => {
    render(<MetricLineChart
      ariaLabel="Динамика выручки"
      emptyText="Нет данных"
      description="Выручка и оплаченные заказы по дням."
      data={points}
      series={[
        { key: "revenue", label: "Выручка", color: "#0f766e", formatValue: (value) => `${value} ₽` },
        { key: "orders", label: "Заказы", color: "#6366f1", axis: "right" },
      ]}
    />)

    const chart = screen.getByRole("figure", { name: "Динамика выручки" })
    expect(screen.getByText("Выручка и оплаченные заказы по дням.")).toBeInTheDocument()
    fireEvent.keyDown(chart, { key: "ArrowRight" })
    expect(screen.getByText("1 августа")).toBeInTheDocument()
    expect(screen.getByText("1000 ₽")).toBeInTheDocument()
  })

  it("shows the supplied empty state", () => {
    render(<MetricLineChart ariaLabel="Пустой график" emptyText="Нет данных" description="Описание" data={[]} series={[]} />)
    expect(screen.getByText("Нет данных")).toBeInTheDocument()
  })
})
