import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { apiRequest } from "../../api/client"
import type { Product } from "../../api/types"
import { ProductsPage } from "./ProductsPage"

const access = vi.hoisted(() => ({ canManage: true }))

vi.mock("../../auth/AuthProvider", () => ({
  useAuth: () => ({ hasPermission: () => access.canManage }),
}))
vi.mock("../../i18n/LanguageProvider", () => ({
  useLanguage: () => ({ locale: "en" }),
}))
vi.mock("../../api/client", async (importOriginal) => ({
  ...await importOriginal<typeof import("../../api/client")>(),
  apiRequest: vi.fn(),
}))
vi.mock("../../components/TableToolbar", async (importOriginal) => ({
  ...await importOriginal<typeof import("../../components/TableToolbar")>(),
  TableToolbar: () => null,
}))

const originalVersion = "2026-10-20T10:00:00Z"
const updatedVersion = "2026-10-20T10:01:00Z"
let product: Product

beforeEach(() => {
  access.canManage = true
  vi.clearAllMocks()
  vi.stubGlobal("matchMedia", () => ({
    matches: false,
    addListener: vi.fn(),
    removeListener: vi.fn(),
  }))
  product = {
    id: 7,
    system_id: "product-7",
    sku: "SKU-7",
    name: "Test product",
    description: null,
    usage: null,
    expiration: null,
    in_stock: true,
    archived: false,
    is_visible_in_app: true,
    priority: 0,
    is_new_manual: false,
    is_new: false,
    discount_percent: "0",
    effective_discount_percent: "0",
    stock_reduction_override: null,
    effective_stock_reduction: 0,
    image_url: "",
    category_ids: [],
    variants: [],
    created_at: originalVersion,
    updated_at: originalVersion,
  }
  vi.mocked(apiRequest).mockImplementation(async (path, init) => {
    if (path === "/products/7/visibility") {
      const body = JSON.parse(String(init?.body)) as { is_visible_in_app: boolean }
      product = { ...product, is_visible_in_app: body.is_visible_in_app, updated_at: updatedVersion }
      return product
    }
    if (path === "/products/stock-visibility/settings") return { enabled: false, reduction: 0, updated_at: null }
    if (path.startsWith("/products?")) return { items: [product], total: 1 }
    if (path.startsWith("/categories?")) return { items: [], total: 0 }
    throw new Error(`Unexpected request: ${path}`)
  })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function renderProducts() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(<QueryClientProvider client={client}><MemoryRouter><ProductsPage /></MemoryRouter></QueryClientProvider>)
}

describe("product storefront visibility", () => {
  it("keeps a hidden product accessible and restores it using its latest version", async () => {
    renderProducts()
    const toggle = await screen.findByRole("switch", { name: "Shown in app: Test product" })
    expect(toggle).toHaveAttribute("aria-checked", "true")
    fireEvent.click(toggle)

    await waitFor(() => expect(toggle).toHaveAttribute("aria-checked", "false"))
    expect(screen.getByText("Hidden")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Merchandising/ })).toBeInTheDocument()
    expect(apiRequest).toHaveBeenCalledWith("/products/7/visibility", {
      method: "PATCH",
      body: JSON.stringify({ is_visible_in_app: false, expected_updated_at: originalVersion }),
    })

    await waitFor(() => expect(toggle).toBeEnabled())
    fireEvent.click(toggle)
    await waitFor(() => expect(toggle).toHaveAttribute("aria-checked", "true"))
    expect(apiRequest).toHaveBeenCalledWith("/products/7/visibility", {
      method: "PATCH",
      body: JSON.stringify({ is_visible_in_app: true, expected_updated_at: updatedVersion }),
    })
  })

  it("shows visibility without a control to staff lacking merchandising permission", async () => {
    access.canManage = false
    product = { ...product, is_visible_in_app: false }
    renderProducts()

    expect(await screen.findByText("Hidden")).toBeInTheDocument()
    expect(screen.queryByRole("switch", { name: "Shown in app: Test product" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /Merchandising/ })).not.toBeInTheDocument()
  })
})
