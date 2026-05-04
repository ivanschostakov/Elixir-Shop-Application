export type ProductRead = {
    id: number
    system_id: string
    sku: string
    name: string
    description: string | null
    usage: string | null
    expiration: string | null
    priority: number
    in_stock: boolean
    archived: boolean
    rating_avg: number
    rating_count: number
    image_url: string
    created_at: string
    updated_at: string
}

export type ProductVariantRead = {
    id: number
    system_id: string
    image_url: string
    sku: string | null
    name: string
    stock: number
    archived: boolean
    price: string
    created_at: string
    updated_at: string
}

export type ProductWithVariantsRead = ProductRead & {
    variants: ProductVariantRead[]
}

export type ProductReviewRead = {
    id: number
    author_username: string
    product_id: number
    value: number
    text: string | null
    answer: string | null
    attachments: ProductReviewAttachmentRead[]
    likes: number
    dislikes: number
    moderated: boolean
    created_at: string
    updated_at: string
}

export type ProductReviewAttachmentRead = {
    id: number
    image_url: string
    created_at: string
    updated_at: string
}

export type UploadableReviewAttachment = {
    uri: string
    fileName?: string | null
    mimeType?: string | null
}

export type ProductReviewCreate = {
    value: number
    text?: string | null
    attachments?: UploadableReviewAttachment[]
}

export type ProductReviewEligibilityRead = {
    can_review: boolean
}

export type ProductCreate = {
    system_id?: string | null
    sku: string
    name: string
    description?: string | null
    usage?: string | null
    expiration?: string | null
    archived?: boolean
    priority?: number
}

export type ProductUpdate = {
    system_id?: string | null
    sku?: string | null
    name?: string | null
    description?: string | null
    usage?: string | null
    expiration?: string | null
    archived?: boolean | null
    priority?: number | null
}
