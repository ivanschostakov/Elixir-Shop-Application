import { mentorText as mt } from "@/i18n/mentor-translations"
import { numeric } from "@/screens/chat/mentor-data"
import type { CompanionAction, CompanionEntry, EntryData, MealType } from "@/services/api/companion"

export function foodDescription(entry?: EntryData | null): string {
    return entry?.note?.trim() || [entry?.name?.trim(), entry?.portion_g ? mt("{0} г", [entry.portion_g]) : ""].filter(Boolean).join(", ")
}

export function appendFoodDictation(text: string, dictated: string): string {
    return [text.trim(), dictated.trim()].filter(Boolean).join(" ").slice(0, 4000)
}

export function foodSaveAction(estimate: EntryData, description: string, key: string, original?: CompanionEntry, now = new Date(), mealType?: MealType, mealKey?: string): CompanionAction {
    const water = estimate.water_ml
    const validWater = water == null || Number.isInteger(water) && water > 0 && water <= 10000
    const valid = validWater && (estimate.kind === "water" ? water != null : estimate.kind === "meal" && !!estimate.name?.trim() && !!estimate.nutrition && (["kcal", "protein", "fat", "carbs"] as const).every(key => { const value = numeric(estimate.nutrition?.[key]); return value !== null && value >= 0 }))
    if (!valid) throw new Error(mt("Не удалось рассчитать КБЖУ. Уточните описание еды."))
    if (original?.kind && original.kind !== estimate.kind) throw new Error(mt("Нельзя менять тип существующей записи"))
    if (estimate.kind === "water") return { kind: "entry", request_key: key, record_now: !original, ...(original ? { resource_id: original.id, expected_version: original.version } : {}), entry: { kind: "water", occurred_at: original?.occurred_at ?? estimate.occurred_at ?? now.toISOString(), water_ml: water, note: description.trim(), estimated: true } }
    return { kind: "entry", request_key: key, record_now: !original, ...(original ? { resource_id: original.id, expected_version: original.version } : {}),
        entry: { ...estimate, kind: "meal", occurred_at: original?.occurred_at ?? estimate.occurred_at ?? now.toISOString(), meal_type: mealType ?? original?.data.meal_type ?? null, meal_key: (mealType ?? original?.data.meal_type) === "extra" ? mealKey ?? original?.data.meal_key ?? key : null, note: description.trim(), favorite: original?.data.favorite ?? false, estimated: true } }
}
