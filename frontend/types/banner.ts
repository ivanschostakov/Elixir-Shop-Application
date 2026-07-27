export type Banner = {
    id: number
    image_path: string
    desktop_image_path: string | null
    mobile_image_path: string | null
    title: string | null
    inner_link: string | null
    outer_link: string | null
    priority: number
    archived: boolean
    status: "draft" | "scheduled" | "published" | "archived"
    starts_at: string | null
    ends_at: string | null
    click_count: number
    impression_count: number
    created_at: string
    updated_at: string
}
