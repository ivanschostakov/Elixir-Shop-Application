import { apiGet, apiPost, apiPostMultipart } from "@/services/api/client"
import { aiChatEndpoint } from "@/services/api/ai-chat.constants"
import { ensureAiDataConsent } from "@/services/api/ai-data-consent"
import { mentorText as mt } from "@/i18n/mentor-translations"
import type {
    AIChatActionPayload,
    AIChatActionResponse,
    AIChatResponse,
    AIChatTranscriptionResponse,
    UploadableChatAttachment,
} from "@/services/api/ai-chat.types"

function scopedChat(response: AIChatResponse, mentor: boolean): AIChatResponse {
    if (response?.chat && response.chat.scope !== (mentor ? "mentor" : "ordinary")) throw new Error(mt("Не удалось загрузить чат. Попробуйте ещё раз."))
    return response
}

export async function getMyAiChat(mentor = false): Promise<AIChatResponse> {
    return scopedChat(await apiGet<AIChatResponse>(mentor ? `${aiChatEndpoint}/companion/messages` : aiChatEndpoint, undefined, { appIntegrityAction: mentor ? "ai-companion" : "ai-chat:read" }), mentor)
}

export async function sendMyAiChatMessage(text: string, attachments: UploadableChatAttachment[] = [], companionRequestId?: string, dialogueProtocol: 1 | 2 = 2, ordinaryChat = false): Promise<AIChatResponse> {
    await ensureAiDataConsent()
    const formData = new FormData()
    formData.append("text", text)
    if (companionRequestId) formData.append("client_request_id", companionRequestId)
    if (companionRequestId) {
        if (dialogueProtocol !== 2) throw new Error("Обновите клиент наставника: требуется протокол 2.")
        formData.append("dialogue_protocol", "2")
    }
    if (ordinaryChat && !companionRequestId) formData.append("chat_mode", "ordinary")

    for (const attachment of attachments) {
        formData.append(
            "attachments",
            {
                uri: attachment.uri,
                name: attachment.fileName ?? "attachment",
                type: attachment.mimeType ?? "application/octet-stream",
            } as unknown as Blob,
        )
    }

    return scopedChat(await apiPostMultipart<AIChatResponse>(companionRequestId ? `${aiChatEndpoint}/companion/messages` : aiChatEndpoint, formData, { appIntegrityAction: companionRequestId ? "ai-companion" : "ai-chat:send" }), !!companionRequestId)
}

export function performAiChatAction(payload: AIChatActionPayload): Promise<AIChatActionResponse> {
    return apiPost<AIChatActionResponse, AIChatActionPayload>(`${aiChatEndpoint}/actions`, payload, { appIntegrityAction: "ai-chat:action" })
}

export async function transcribeMyAiChatVoice(audio: UploadableChatAttachment): Promise<AIChatTranscriptionResponse> {
    await ensureAiDataConsent()
    const formData = new FormData()
    formData.append(
        "audio",
        {
            uri: audio.uri,
            name: audio.fileName ?? "voice.m4a",
            type: audio.mimeType ?? "audio/m4a",
        } as unknown as Blob,
    )

    return apiPostMultipart<AIChatTranscriptionResponse>(`${aiChatEndpoint}/transcribe`, formData, { appIntegrityAction: "ai-chat:transcribe" })
}
