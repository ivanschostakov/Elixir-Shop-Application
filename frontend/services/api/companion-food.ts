import { apiPostMultipart } from "@/services/api/client"
import { aiChatEndpoint } from "@/services/api/ai-chat.constants"
import { ensureAiDataConsent } from "@/services/api/ai-data-consent"
import type { UploadableChatAttachment } from "@/services/api/ai-chat.types"
import type { EntryData } from "@/services/api/companion"

export type FoodEstimate = { entry: EntryData | null; message: string }

export async function estimateCompanionFood(text: string, photo: UploadableChatAttachment | null, key: string, previousPhotoId?: number): Promise<FoodEstimate> {
    await ensureAiDataConsent()
    const form = new FormData()
    form.append("text", text.trim())
    form.append("client_request_id", key)
    if (previousPhotoId && !photo) form.append("photo_attachment_id", String(previousPhotoId))
    if (photo) form.append("attachments", { uri: photo.uri, name: photo.fileName ?? "food.jpg", type: photo.mimeType ?? "image/jpeg" } as unknown as Blob)
    return apiPostMultipart<FoodEstimate>(`${aiChatEndpoint}/companion/meal-estimate`, form, { appIntegrityAction: "ai-companion", timeoutMs: 550000 })
}

export async function askNutritionHelp(mode: "suggest" | "product", text: string, photo: UploadableChatAttachment | null, key: string): Promise<FoodEstimate> {
    await ensureAiDataConsent()
    const form = new FormData()
    form.append("mode", mode); form.append("text", text.trim()); form.append("client_request_id", key)
    if (photo) form.append("attachments", { uri: photo.uri, name: photo.fileName ?? "food.jpg", type: photo.mimeType ?? "image/jpeg" } as unknown as Blob)
    return apiPostMultipart<FoodEstimate>(`${aiChatEndpoint}/companion/nutrition-help`, form, { appIntegrityAction: "ai-companion", timeoutMs: 550000 })
}
