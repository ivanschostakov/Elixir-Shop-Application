import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"
import { LanguageProvider } from "../i18n/LanguageProvider"
import { MediaThumbnail } from "./MediaThumbnail"

const tile = (src?: string) => <LanguageProvider><MediaThumbnail src={src} size={124} alt="Attachment" /></LanguageProvider>
afterEach(cleanup)

describe("review attachments", () => {
  it("loads public review media from the admin origin and keeps its cache version", () => {
    render(tile("https://api.example.test/media/reviews/3/photo.jpg?v=23"))
    expect(screen.getByAltText("Attachment")).toHaveAttribute("src", "/media/reviews/3/photo.jpg?v=23")
  })
  it("shows a readable missing state and retries when a different file is selected", () => {
    const { rerender } = render(tile("/media/reviews/3/missing.jpg"))
    fireEvent.error(screen.getByAltText("Attachment"))
    expect(screen.queryByAltText("Attachment")).toBeNull()
    expect(screen.getByRole("img", { name: "Attachment" })).toHaveTextContent("Нет изображения")
    rerender(tile("/media/reviews/3/other.jpg"))
    expect(screen.getByAltText("Attachment")).toHaveAttribute("src", "/media/reviews/3/other.jpg")
  })
})
