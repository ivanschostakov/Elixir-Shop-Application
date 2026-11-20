import { mentorText as mt } from "@/i18n/mentor-translations"
import { numeric } from "@/screens/chat/mentor-data"
import type { CompanionAction, CompanionEntry, EntryData } from "@/services/api/companion"

export function foodDescription(entry?: EntryData | null): string {
    return entry?.note?.trim() || [entry?.name?.trim(), entry?.portion_g ? mt("{0} г", [entry.portion_g]) : ""].filter(Boolean).join(", ")
}

export function appendFoodDictation(text: string, dictated: string): string {
    return [text.trim(), dictated.trim()].filter(Boolean).join(" ").slice(0, 4000)
}

export function foodSaveAction(estimate: EntryData, description: string, key: string, original?: CompanionEntry, now = new Date()): CompanionAction {
    if (estimate.kind !== "meal" || !estimate.name?.trim() || !estimate.nutrition || (["kcal", "protein", "fat", "carbs"] as const).some(key => { const value = numeric(estimate.nutrition?.[key]); return value === null || value < 0 })) throw new Error(mt("Не удалось рассчитать КБЖУ. Уточните описание еды."))
    return { kind: "entry", request_key: key, ...(original ? { resource_id: original.id, expected_version: original.version } : {}),
        entry: { ...estimate, kind: "meal", occurred_at: original?.occurred_at ?? now.toISOString(), note: description.trim(), favorite: original?.data.favorite ?? false, estimated: true } }
}
