import { ApiError, apiDelete, apiGet, apiPost } from "@/services/api/client"
import { aiChatEndpoint } from "@/services/api/ai-chat.constants"
import type { AIAttachmentRead } from "@/services/api/ai-chat.types"

export type Numeric = number | string
export type Nutrition = { kcal: Numeric; protein: Numeric; fat: Numeric; carbs: Numeric }
export type ProfileData = {
    goal?: "weight_loss" | "weight_gain" | "custom" | "maintain" | "course"; custom_goal?: string; workout_plan?: WorkoutPlan | null; age?: number | null; sex?: "male" | "female" | null
    height_cm?: Numeric | null; target_weight_kg?: Numeric | null; activity?: "low" | "light" | "moderate" | "high" | null
    preferences?: string; restrictions?: string; nutrition?: Nutrition | null
    nutrition_source?: "manual" | "calculated"; nutrition_rule_version?: string | null
}
export type CompanionSettings = {
    timezone: string; nutrition_auto_eligible: boolean; course_reminders: boolean; daily_time: string | null; weight_time: string | null
    weekly_time: string | null; weekly_day: number; supply_reminders: boolean; supply_days: number
    checkin_time?: string | null; checkin_topics?: ("course" | "nutrition" | "weight" | "wellbeing")[]; inactivity_days?: number | null; inactivity_time?: string
}
export type Unit = "mg" | "mcg" | "g" | "ml" | "capsule" | "tablet" | "IU"
export type Stage = { start_date: string; end_date: string; amount: Numeric; unit: Unit; interval_days: number; weekdays: number[]; times: string[] }
export type CourseItem = {
    name: string; variant_id?: number | null; stages: Stage[]; package_amount?: Numeric | null
    package_unit?: Unit | null; home_amount: Numeric | null; package_source_name?: string | null
}
export type PlanData = { name: string; timezone: string; items: CourseItem[]; source?: "user_supplied_plan" | "ai_recommended_plan" }
export type WorkoutPlan = { name: string; start_date: string; end_date: string | null; days: { key: string; name: string; weekdays: number[]; exercises: { key: string; name: string; sets: number; target_reps: number | null; target_weight_kg: Numeric | null }[] }[] }
export type Workout = { name: string; plan_day_key: string | null; scheduled_date: string | null; status: "in_progress" | "completed"; duration_seconds: number; current_exercise_index: number; exercises: { key: string; name: string; sets: { weight_kg: Numeric | null; reps: number | null; completed: boolean }[] }[] }
export type Measurement = { waist_cm?: Numeric | null; chest_cm?: Numeric | null; hips_cm?: Numeric | null; arm_cm?: Numeric | null; thigh_cm?: Numeric | null; body_fat_percent?: Numeric | null }
export type EntryData = {
    kind: "meal" | "weight" | "wellbeing" | "workout" | "measurement" | "progress_photo"; occurred_at: string; name?: string | null; portion_g?: Numeric | null
    nutrition?: Nutrition | null; weight_kg?: Numeric | null; wellbeing?: number | null; appetite?: number | null
    energy?: number | null; sleep_hours?: Numeric | null; note?: string; estimated?: boolean; assumptions?: string
    workout?: Workout | null; measurement?: Measurement | null; favorite?: boolean
    photo_attachment_ids?: number[]
}
export type Proposal = { kind: "profile" | "plan" | "entry" | "nutrition"; summary: string; profile?: ProfileData | null; plan?: PlanData | null; entry?: EntryData | null; nutrition?: Nutrition | null }
export type CompanionCard = { id: string; kind: Proposal["kind"]; summary: string; proposal: Proposal; state: "pending" | "confirmed" | "cancelled"; action_token: string | null; profile_version: number }
export type CompanionEntry = { id: number; version: number; kind: EntryData["kind"]; occurred_at: string; data: EntryData; photo_attachments?: AIAttachmentRead[]; unavailable_photo_attachment_ids?: number[] }
export type CompanionEvent = { id: number; version: number; scheduled_at: string; status: "pending" | "done" | "skipped"; data: { name: string; amount: Numeric; unit: Unit } }
export type ProgressTotals = { workouts: { sessions: number; completed: number; in_progress: number; completed_sets: number; reps: number; volume_kg: Numeric; duration_seconds: number }; measurements: { count: number; latest: Measurement; change: Measurement }; wellbeing: { entries: number; average_score: Numeric | null; average_energy?: Numeric | null; energy_measurements?: number } }
export type Summary = { nutrition: Nutrition; meals_logged: number; days_with_meals: number; weight_measurements: number; weight_change_kg: string | null; events: { done: number; skipped: number; pending: number }; coverage_note: string } & Partial<ProgressTotals>
export type CompanionState = {
    mentor?: MentorDashboard | null
    dialogue_protocol?: 1 | 2
    available: boolean; consent_version: string; consent_required?: boolean
    profile?: { id: number; enabled: boolean; version: number; data: ProfileData; settings: CompanionSettings } | null
    plan?: { id: number; version: number; status: string; data: PlanData } | null
    events?: CompanionEvent[]; entries?: CompanionEntry[]; today?: Summary
}
export type MentorTask = { id: string; kind: "course" | "workout"; label: string; status: "pending" | "done" | "skipped" | "in_progress"; resource_id: number | null; version: number | null; scheduled_at: string | null; plan_day_key: string | null }
export type MentorDashboard = {
    latest_weight: CompanionEntry | null
    workout_plan: WorkoutPlan | null
    today: { date: string; course: { scheduled: number; done: number; skipped: number; pending: number }; workouts: { scheduled: number; completed: number; in_progress: number }; tasks: MentorTask[]; nutrition: { consumed: Nutrition; target: Nutrition | null; remaining: Nutrition | null } }
    week: { from_date: string; to_date: string; summary: Summary & ProgressTotals }
}
export type CompanionAction = {
    request_key?: string; kind: "enable" | "disable" | "profile" | "settings" | "plan" | "plan_status" | "entry" | "delete_entry" | "event" | "confirm" | "cancel" | "nutrition" | "dialogue_confirm" | "dialogue_cancel" | "dialogue_edit" | "dialogue_undo" | "workout_plan"
    workout_plan?: WorkoutPlan | null
    expected_version?: number; resource_id?: number; profile?: ProfileData; settings?: CompanionSettings; plan?: PlanData
    entry?: EntryData; nutrition?: Nutrition; nutrition_rule_version?: string; status?: string; message_id?: number; action_id?: string; action_token?: string
    consent_version?: string; adult_confirmed?: boolean
}
export type SupplyItem = { name: string; variant_id?: number | null; available: boolean; reason?: string; required?: string; home_remaining?: string; unit?: Unit; packages?: number; price?: string | null; stock?: number | null; estimated_cost?: string | null; projected_shortage_at?: string | null }
export type Supply = { available: boolean; reason?: string; days?: number; items?: SupplyItem[]; note?: string }

const endpoint = `${aiChatEndpoint}/companion`
const proof = { appIntegrityAction: "ai-companion" }
export const requestKey = () => `comp-${Date.now()}-${Math.random().toString(36).slice(2, 14)}`
export type DialogueCard = {
    children?: DialogueCard[]
    changes?: { parameter: string; before: unknown; after: unknown }[]
    id: string; kind: string; summary: string; action_token: string; can_undo: boolean; error?: string
    state: "pending" | "saved" | "cancelled" | "superseded" | "undone" | "needs_correction"
    operation: {
        operations?: DialogueCard["operation"][]
        kind: string; plan?: PlanData | null; entry?: EntryData | null; profile?: ProfileData | null; nutrition?: Nutrition | null
        settings?: CompanionSettings & { checkin_time?: string | null } | null; status?: string | null
        remind_course?: boolean | null
        intake?: { name: string; local_date: string; occurred_at?: string | null; period: string; amount?: Numeric | null; unit?: Unit | null; note?: string } | null
    }
}
export const companionDialogue = (kind: "intro" | "course" | "nutrition" | "progress", days: 7 | 30 = 7, key = requestKey()) => apiPost(`${endpoint}/dialogue`, { request_key: key, kind, days }, proof)
export async function getCompanionAvailability(): Promise<CompanionState> {
    try { return await apiGet<CompanionState>(`${endpoint}/availability`) }
    catch (error) {
        // A compatible OTA may arrive before the backend rollout, or survive its rollback.
        if (error instanceof ApiError && error.status === 404) return { available: false, consent_version: "" }
        throw error
    }
}
export const getCompanion = () => apiGet<CompanionState>(endpoint, undefined, proof)
export const syncCompanionTimezone = () => apiPost<{ ok: boolean }, Record<string, never>>(`${endpoint}/timezone`, {}, proof)
export const actCompanion = (payload: CompanionAction) => apiPost<{ state: CompanionState }, CompanionAction>(`${endpoint}/actions`, { ...payload, request_key: payload.request_key ?? requestKey() }, proof)
export const eraseCompanion = () => apiDelete(`${endpoint}?confirm=true`, proof)
export const getCompanionSummary = (from: string, to: string) => apiGet<Summary>(`${endpoint}/summary`, { from_date: from, to_date: to }, proof)
export const getCompanionEntries = (from: string, to: string, kind?: EntryData["kind"]) => apiGet<{ entries: CompanionEntry[] }>(`${endpoint}/entries`, { from_date: from, to_date: to, ...(kind ? { kind } : {}) }, proof)
export const getCompanionProgressPhotos = (from: string, to: string) => apiGet<{ entries: CompanionEntry[]; limit: number; may_have_more: boolean }>(`${endpoint}/progress-photos`, { from_date: from, to_date: to }, proof)
export const getCompanionFavoriteMeals = () => apiGet<{ entries: CompanionEntry[]; limit: number; may_have_more: boolean }>(`${endpoint}/favorite-meals`, undefined, proof)
export const getCompanionEvents = (from: string, to: string) => apiGet<{ events: CompanionEvent[] }>(`${endpoint}/events`, { from_date: from, to_date: to }, proof)
export const getCompanionSupply = (days = 30) => apiGet<Supply>(`${endpoint}/supply`, { days }, proof)
export const getNutritionSuggestion = () => apiGet<{ available: boolean; reason?: string; nutrition?: Nutrition; rule_version?: string; note?: string; maintenance_kcal?: string; deficit_kcal?: string; surplus_kcal?: string }>(`${endpoint}/nutrition`, undefined, proof)
