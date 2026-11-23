import { apiGet, apiPostMultipart } from "@/services/api/client"
import { aiChatEndpoint } from "@/services/api/ai-chat.constants"
import { ensureAiDataConsent } from "@/services/api/ai-data-consent"
import type { UploadableChatAttachment } from "@/services/api/ai-chat.types"
import type { CompanionEntry, WorkoutPlan } from "@/services/api/companion"

export type WorkoutSetup = {
    goal: "muscle" | "strength" | "endurance" | "maintain"
    experience: "beginner" | "some" | "advanced"
    place: "gym" | "home" | "outdoors"
    equipment: ("dumbbells" | "barbell" | "machines" | "bands" | "pullup" | "bodyweight")[]
    weekdays: number[]; minutes: number; preferences: string
}
export type WorkoutDraftRequest = { mode: "generate" | "import" | "revise"; language: "ru" | "en" | "kz"; start_date: string; text: string; setup?: WorkoutSetup | null; current_plan?: WorkoutPlan | null }
export type WorkoutDraftResult = { plan: WorkoutPlan | null; message: string; questions: string[] }
const endpoint = `${aiChatEndpoint}/companion`
const proof = { appIntegrityAction: "ai-companion" }

export const getWorkoutLibrary = (from: string, to: string) => apiGet<{ entries: CompanionEntry[]; may_have_more: boolean }>(`${endpoint}/workouts`, { from_date: from, to_date: to }, proof)

export async function requestWorkoutDraft(request: WorkoutDraftRequest, photos: UploadableChatAttachment[], key: string): Promise<WorkoutDraftResult> {
    await ensureAiDataConsent()
    const form = new FormData()
    form.append("payload", JSON.stringify(request)); form.append("client_request_id", key)
    for (const photo of photos) form.append("attachments", { uri: photo.uri, name: photo.fileName ?? "training.jpg", type: photo.mimeType ?? "image/jpeg" } as unknown as Blob)
    return apiPostMultipart<WorkoutDraftResult>(`${endpoint}/workout-draft`, form, { ...proof, timeoutMs: 550000 })
}
