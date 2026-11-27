import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"
import { apiRequest } from "../api/client"
import { LanguageProvider } from "../i18n/LanguageProvider"
import { SupportReplyComposer } from "./CommunicationsPage"

vi.mock("../api/client", async original => ({
  ...await original<typeof import("../api/client")>(), apiRequest: vi.fn(),
}))
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals() })

it("sends the selected PDF to the selected conversation as an internal file-only note", async () => {
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} })
  vi.mocked(apiRequest).mockResolvedValue({ id: 32 })
  const client = new QueryClient()
  const { container } = render(<QueryClientProvider client={client}><LanguageProvider>
    <SupportReplyComposer conversationId={32} copy={{ note: "Internal", reply: "Reply", send: "Send" }} />
  </LanguageProvider></QueryClientProvider>)
  const send = screen.getByRole("button", { name: /Send/ })
  expect(send).toBeDisabled()
  fireEvent.click(screen.getByRole("switch"))
  fireEvent.change(container.querySelector('input[type=file]')!, {
    target: { files: [new File(["%PDF-1.4"], "invoice.pdf", { type: "application/pdf" })] },
  })
  await waitFor(() => expect(send).toBeEnabled())
  fireEvent.click(send)
  await waitFor(() => expect(apiRequest).toHaveBeenCalledOnce())
  const [path, init] = vi.mocked(apiRequest).mock.calls[0]
  expect(path).toBe("/support/conversations/32/messages/with-files")
  const body = init?.body as FormData
  expect(body.get("is_internal")).toBe("true")
  expect((body.get("attachments") as File).name).toBe("invoice.pdf")
  await waitFor(() => expect(send).toBeDisabled())
})
