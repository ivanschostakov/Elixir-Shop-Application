import type { UploadableChatAttachment } from "@/services/api/ai-chat.types"

export type SupportConversationStatus = "new" | "open" | "waiting_customer" | "waiting_team" | "resolved" | "spam"
export type SupportPriority = "low" | "normal" | "high" | "urgent"

export type SupportAttachment = {
    id: number
    original_filename: string
    mime_type: string
    size_bytes: number
    download_url: string
}

export type SupportMessage = {
    id: number
    sender_type: "user" | "admin" | "system"
    body: string
    author_name: string
    author_role: string | null
    is_internal: boolean
    delivered_at: string | null
    read_at: string | null
    attachments: SupportAttachment[]
    created_at: string
    updated_at: string
}

export type SupportConversationSummary = {
    id: number
    subject: string | null
    status: SupportConversationStatus
    priority: SupportPriority
    assignee_name: string | null
    customer_unread_count: number
    last_message_at: string | null
    created_at: string
    updated_at: string
}

export type SupportConversation = SupportConversationSummary & {
    messages: SupportMessage[]
}

export type SupportInbox = {
    active: SupportConversation | null
    previous: SupportConversationSummary[]
    total_unread: number
}

export type CreateSupportConversationPayload = {
    client_message_id: string
    subject?: string | null
    message: string
}

export type SendSupportMessagePayload = {
    clientMessageId: string
    message: string
    attachments?: UploadableChatAttachment[]
}
