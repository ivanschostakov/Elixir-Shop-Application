import { mentorText as mt } from "@/i18n/mentor-translations"
import { formatCompanionDate } from "@/screens/chat/companion-timezones"
import { numeric } from "@/screens/chat/mentor-data"
import type { CompanionEntry, CompanionState, MealType, Nutrition } from "@/services/api/companion"

export const mainMeals = ["breakfast", "lunch", "dinner"] as const
export const mealLabel = (type: MealType) => ({ breakfast: mt("Завтрак"), lunch: mt("Обед"), dinner: mt("Ужин"), extra: mt("Ещё приём пищи") })[type]
export function suggestedMeal(clock: string, at = new Date().toISOString()): MealType {
    const hour = Number(formatCompanionDate(at, clock).match(/(\d{2}):\d{2}/)?.[1] ?? 12)
    return hour < 11 ? "breakfast" : hour < 17 ? "lunch" : "dinner"
}
export const entryMeal = (entry: CompanionEntry, clock: string) => entry.data.meal_type ?? suggestedMeal(clock, entry.occurred_at)
export function mealTotals(entries: CompanionEntry[]): Nutrition {
    return Object.fromEntries((["kcal", "protein", "fat", "carbs"] as const).map(key => [key, entries.reduce((sum, entry) => sum + Math.max(0, numeric(entry.data.nutrition?.[key]) ?? 0), 0)])) as Nutrition
}
export function mealGroups(entries: CompanionEntry[], clock: string) {
    const groups: { type: MealType; key?: string; entries: CompanionEntry[]; total: Nutrition }[] = mainMeals.map(type => ({ type, entries: [], total: mealTotals([]) }))
    for (const entry of entries) {
        const type = entryMeal(entry, clock), key = type === "extra" ? entry.data.meal_key ?? `entry-${entry.id}` : undefined
        let group = groups.find(group => group.type === type && group.key === key)
        if (!group) { group = { type, key, entries: [], total: mealTotals([]) }; groups.push(group) }
        group.entries.push(entry)
    }
    for (const group of groups) group.total = mealTotals(group.entries)
    return groups
}
export const waterTarget = (state: CompanionState | null) => state?.mentor?.today?.water?.target_ml ?? state?.profile?.settings?.water_goal_ml ?? (state?.profile?.data.sex === "female" ? 1600 : 2000)
export const needsFoodDetails = (text: string, hasPhoto: boolean) => {
    const describedWater = /\d+(?:[.,]\d+)?\s*(?:мл|ml|л|l)(?!\p{L})/iu.test(text) && /(?:^|\s)(?:вод[ауы]|water|су)(?:$|[\s.!?,])/iu.test(text)
    return !hasPhoto && !describedWater && text.trim().split(/\s+/).filter(Boolean).length < 4
}
