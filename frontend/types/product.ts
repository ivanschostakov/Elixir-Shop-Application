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
    price: string
    created_at: string
    updated_at: string
}

export type ProductWithVariantsRead = ProductRead & {
    variants: ProductVariantRead[]
}

export type ProductCreate = {
    system_id?: string | null
    sku: string
    name: string
    description?: string | null
    usage?: string | null
    expiration?: string | null
    priority?: number
}

export type ProductUpdate = {
    system_id?: string | null
    sku?: string | null
    name?: string | null
    description?: string | null
    usage?: string | null
    expiration?: string | null
    priority?: number | null
}
