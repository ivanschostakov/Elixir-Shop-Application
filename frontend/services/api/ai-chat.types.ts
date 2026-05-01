import type { BasketRead } from "@/types/basket"

export type BotModel = "free" | "premium"
export type MessageSender = "user" | "ai"
export type AttachmentType = "document" | "image"
export type AIActionType = "open_product" | "open_checkout" | "ask_ai" | "add_to_basket"
export type AIActionStyle = "primary" | "secondary" | "link"
export type AIProductIntent = "recommend" | "compare" | "alternative"

export type AIInteractiveAction = {
    id: string
    type: AIActionType
    label: string
    style: AIActionStyle
    product_id: number | null
    variant_id: number | null
    quantity: number | null
    prompt: string | null
    action_token: string | null
    completed: boolean
    created_basket_item_id: number | null
}

export type AIInteractiveVariant = {
    id: number
    sku: string | null
    name: string
    stock: number
    price: string
    image_url: string
    in_stock: boolean
}

export type AIInteractiveActionRow = {
    action_ids: string[]
}

export type AIInteractiveProductCard = {
    id: string
    product_id: number
    intent: AIProductIntent
    title: string
    reason: string | null
    image_url: string
    in_stock: boolean
    variants: AIInteractiveVariant[]
    actions: AIInteractiveAction[]
    action_rows?: AIInteractiveActionRow[]
}

export type AIInteractivePayload = {
    cards: AIInteractiveProductCard[]
}

export type AIAttachmentRead = {
    id: number
    message_id: number
    type: AttachmentType
    original_filename: string | null
    filename: string
    mime_type: string | null
    size_bytes: number
    relative_path: string
    created_at: string
    updated_at: string
}

export type AIMessageRead = {
    id: number
    user_id: number
    chat_id: number
    text: string
    sender: MessageSender
    bot_model: BotModel
    tokens: number
    attachments: AIAttachmentRead[]
    interactive: AIInteractivePayload | null
    created_at: string
    updated_at: string
}

export type AIChatRead = {
    id: number
    user_id: number
    conversation_id: string
    current_tokens: number
    total_tokens: number
    messages: AIMessageRead[]
    created_at: string
    updated_at: string
}

export type AIChatTurnMetaRead = {
    selected_bot_model: BotModel
    input_tokens: number
    cached_input_tokens: number
    output_tokens: number
    conversation_reset_reason: string | null
}

export type AIChatResponse = {
    chat: AIChatRead
    last_turn: AIChatTurnMetaRead | null
    basket: BasketRead | null
}

export type AIChatActionPayload = {
    message_id: number
    action_id: string
    action_token: string
    quantity?: number
}

export type AIChatActionResponse = AIChatResponse & {
    basket_item_id: number | null
}

export type AIChatTranscriptionResponse = {
    text: string
}

export type UploadableChatAttachment = {
    uri: string
    fileName?: string | null
    mimeType?: string | null
}
