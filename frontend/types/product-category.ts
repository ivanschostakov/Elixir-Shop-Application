export type ProductCategory = {
    id: number
    name: string
    description: string | null
    archived: boolean
    is_visible_in_app: boolean
    app_display_order: number
    discount_percent: string
    created_at: string
    updated_at: string
}
