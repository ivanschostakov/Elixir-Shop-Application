import { apiGet, apiPost, apiPostMultipart } from "@/services/api/client"
import { aiChatEndpoint } from "@/services/api/ai-chat.constants"
import type {
    AIChatActionPayload,
    AIChatActionResponse,
    AIChatResponse,
    AIChatTranscriptionResponse,
    UploadableChatAttachment,
} from "@/services/api/ai-chat.types"

export function getMyAiChat(): Promise<AIChatResponse> {
    return apiGet<AIChatResponse>(aiChatEndpoint, undefined, { appIntegrityAction: "ai-chat:read" })
}

export function sendMyAiChatMessage(text: string, attachments: UploadableChatAttachment[] = []): Promise<AIChatResponse> {
    const formData = new FormData()
    formData.append("text", text)

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

    return apiPostMultipart<AIChatResponse>(aiChatEndpoint, formData, { appIntegrityAction: "ai-chat:send" })
}

export function performAiChatAction(payload: AIChatActionPayload): Promise<AIChatActionResponse> {
    return apiPost<AIChatActionResponse, AIChatActionPayload>(`${aiChatEndpoint}/actions`, payload, { appIntegrityAction: "ai-chat:action" })
}

export function transcribeMyAiChatVoice(audio: UploadableChatAttachment): Promise<AIChatTranscriptionResponse> {
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
