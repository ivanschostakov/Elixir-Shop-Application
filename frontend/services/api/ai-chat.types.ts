export type BotModel = "free" | "premium"
export type MessageSender = "user" | "ai"
export type AttachmentType = "document" | "image"

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
}

export type AIChatTranscriptionResponse = {
    text: string
}

export type UploadableChatAttachment = {
    uri: string
    fileName?: string | null
    mimeType?: string | null
}
