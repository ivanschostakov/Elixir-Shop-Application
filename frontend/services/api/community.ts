import { apiGet, apiPost, apiPostMultipart } from "@/services/api/client"
import type { CommunityMessage, CommunityMessagePage, CommunityStatus, CommunityTopicList, SendCommunityMessagePayload } from "@/services/api/community.types"

const communityEndpoint = "/v1/users/me/community"
const readOptions = { appIntegrityAction: "community:read" }

export function getCommunityStatus(refresh = false) {
    return apiGet<CommunityStatus>(`${communityEndpoint}/status`, refresh ? { refresh: true } : undefined, readOptions)
}

export function getCommunityTopics() {
    return apiGet<CommunityTopicList>(`${communityEndpoint}/topics`, undefined, readOptions)
}

export function getCommunityMessages(topicId: number, options: { beforeId?: number; afterId?: number; limit?: number } = {}) {
    return apiGet<CommunityMessagePage>(`${communityEndpoint}/topics/${topicId}/messages`, { before_id: options.beforeId, after_id: options.afterId, limit: options.limit ?? 50 }, readOptions)
}

export function sendCommunityMessage(topicId: number, payload: SendCommunityMessagePayload) {
    const formData = new FormData()
    formData.append("client_id", payload.clientId)
    formData.append("text", payload.text)
    if (payload.replyToMessageId) formData.append("reply_to_message_id", String(payload.replyToMessageId))
    for (const attachment of payload.attachments ?? []) {
        formData.append("attachments", { uri: attachment.uri, name: attachment.fileName ?? "attachment", type: attachment.mimeType ?? "application/octet-stream" } as unknown as Blob)
    }
    return apiPostMultipart<CommunityMessage>(`${communityEndpoint}/topics/${topicId}/messages`, formData, { appIntegrityAction: "community:send" })
}

export function markCommunityTopicRead(topicId: number, lastMessageId: number) {
    return apiPost<{ ok: boolean }, { last_message_id: number }>(`${communityEndpoint}/topics/${topicId}/read`, { last_message_id: lastMessageId }, readOptions)
}
