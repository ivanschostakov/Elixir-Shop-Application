import { apiPost, apiPostMultipart } from "@/services/api/client"
import { aiChatEndpoint } from "@/services/api/ai-chat.constants"
import { ensureAiDataConsent } from "@/services/api/ai-data-consent"
import type { UploadableChatAttachment } from "@/services/api/ai-chat.types"
import type { EntryData, MealType, Nutrition } from "@/services/api/companion"

export type FoodSuggestion = {
    name: string; description: string; portion: string; nutrition: Nutrition; minutes: number
    ingredients: string[]; steps: string[]; image_query: string
    image: { url: string; source_url: string; author: string; license: string } | null
}
export type MealSuggestionContext = { meal_type: MealType; meals_left: number; remaining: Nutrition | null; budget: Nutrition | null }
export type FoodEstimate = { entry: EntryData | null; message: string; suggestions?: FoodSuggestion[]; next_meal?: MealSuggestionContext | null }

export async function estimateCompanionFood(text: string, photo: UploadableChatAttachment | null, key: string, previousPhotoId?: number, context?: { original_id?: number; original_version?: number; meal_type?: MealType; meal_key?: string }): Promise<FoodEstimate> {
    await ensureAiDataConsent()
    const form = new FormData()
    form.append("text", text.trim())
    form.append("client_request_id", key)
    if (context) for (const [key, value] of Object.entries(context)) if (value != null) form.append(key, String(value))
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

export const markFoodEstimateSeen = (key: string) => apiPost(`${aiChatEndpoint}/companion/meal-estimate/${encodeURIComponent(key)}/seen`, {}, { appIntegrityAction: "ai-companion" })
