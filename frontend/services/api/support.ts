import { ENDPOINTS } from "@/services/api/constants"
import { apiGet, apiPost, apiPostMultipart } from "@/services/api/client"
import type {
    CreateSupportConversationPayload,
    SendSupportMessagePayload,
    SupportConversation,
    SupportInbox,
} from "@/services/api/support.types"

const supportPath = `${ENDPOINTS.USERS}/me/support`
const integrity = { appIntegrityAction: "support:write" } as const

export function getMySupportInbox() {
    return apiGet<SupportInbox>(supportPath, undefined, { appIntegrityAction: "support:read" })
}

export function getMySupportConversation(conversationId: number) {
    return apiGet<SupportConversation>(
        `${supportPath}/conversations/${conversationId}`,
        undefined,
        { appIntegrityAction: "support:read" },
    )
}

export function createMySupportConversation(payload: CreateSupportConversationPayload) {
    return apiPost<SupportConversation, CreateSupportConversationPayload>(
        `${supportPath}/conversations`,
        payload,
        integrity,
    )
}

export function sendMySupportMessage(conversationId: number, payload: SendSupportMessagePayload) {
    const formData = new FormData()
    formData.append("client_message_id", payload.clientMessageId)
    formData.append("message", payload.message)
    for (const [index, attachment] of (payload.attachments || []).entries()) {
        formData.append("attachments", {
            uri: attachment.uri,
            name: attachment.fileName ?? `support-image-${index + 1}.jpg`,
            type: attachment.mimeType ?? "image/jpeg",
        } as unknown as Blob)
    }
    return apiPostMultipart<SupportConversation>(
        `${supportPath}/conversations/${conversationId}/messages`,
        formData,
        integrity,
    )
}

export function markMySupportConversationRead(conversationId: number) {
    return apiPost<{ conversation_id: number; unread_count: number }, Record<string, never>>(
        `${supportPath}/conversations/${conversationId}/read`,
        {},
        integrity,
    )
}
