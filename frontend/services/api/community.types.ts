import type { UploadableChatAttachment } from "@/services/api/ai-chat.types"

export type CommunityAccess = "granted" | "telegram_link_required" | "membership_required" | "temporarily_unavailable"
export type CommunityDeliveryStatus = "queued" | "sending" | "sent" | "failed" | "delivery_unknown"

export type CommunityStatus = {
    enabled: boolean
    access: CommunityAccess
    group: { title: string; image_url: string | null } | null
    action_url: string | null
}

export type CommunityAuthor = {
    id: number
    full_name: string
    avatar_url: string | null
    is_current_user: boolean
}

export type CommunityAttachment = {
    id: number
    kind: "image" | "document"
    filename: string
    mime_type: string | null
    size_bytes: number
    media_url: string | null
    available_in_telegram: boolean
}

export type CommunityReplyPreview = {
    id: number
    author_name: string
    text: string
}

export type CommunityReaction = {
    emoji: string
    count: number
    reacted_by_me: boolean
}

export type CommunityMessage = {
    id: number
    topic_id: number
    author: CommunityAuthor
    text: string
    attachments: CommunityAttachment[]
    reply_to: CommunityReplyPreview | null
    reactions: CommunityReaction[]
    unsupported_type: string | null
    telegram_url: string | null
    delivery_status: CommunityDeliveryStatus
    is_edited: boolean
    is_deleted: boolean
    can_edit: boolean
    can_delete: boolean
    edited_at: string | null
    created_at: string
}

export type CommunityTopic = {
    id: number
    name: string
    icon_color: number | null
    icon_custom_emoji_id: string | null
    is_closed: boolean
    last_message: CommunityMessage | null
    unread_count: number
}

export type CommunityTopicList = { topics: CommunityTopic[]; total_unread: number }
export type CommunityMessagePage = { messages: CommunityMessage[]; has_more: boolean; oldest_id: number | null; newest_id: number | null; sync_cursor: string; sync_cursor_id: number }

export type SendCommunityMessagePayload = {
    clientId: string
    text: string
    replyToMessageId?: number | null
    attachments?: UploadableChatAttachment[]
}
