import { mentorText as mt, mentorDateLabel } from "@/i18n/mentor-translations"
import { companionCalendarDay, localDateTime, shiftCalendarDay } from "@/screens/chat/companion-timezones"
import type { CompanionAction, CompanionEntry, EntryData } from "@/services/api/companion"

export type WellbeingDraft = {
    wellbeing: number | null
    energy: number | null
    mood: number | null
    stress: number | null
    sleepMinutes: number | null
    sleepQuality: number | null
    appetite: number | null
    note: string
}

export const wellbeingLabels = ["Плохо", "Не очень", "Нормально", "Хорошо", "Отлично"] as const
export const energyLabels = ["Совсем нет сил", "Мало энергии", "Обычный уровень", "Достаточно сил", "Очень много энергии"] as const
export const moodLabels = ["Пониженное", "Ровное", "Приподнятое"] as const
export const stressLabels = ["Спокойно", "Небольшой стресс", "Умеренный стресс", "Сильный стресс", "Очень сильный стресс"] as const
export const sleepQualityLabels = ["Плохо", "Средне", "Хорошо"] as const
export const appetiteLabels = ["Сниженный", "Обычный", "Повышенный"] as const

const inScale = (value: unknown, max: number): value is number => typeof value === "number" && Number.isInteger(value) && value >= 1 && value <= max
export function wellbeingDraft(data?: EntryData): WellbeingDraft {
    const hours = data?.sleep_hours == null ? null : Number(data.sleep_hours)
    return {
        wellbeing: inScale(data?.wellbeing, 5) ? data.wellbeing : null,
        energy: inScale(data?.energy, 5) ? data.energy : null,
        mood: inScale(data?.mood, 3) ? data.mood : null,
        stress: inScale(data?.stress, 5) ? data.stress : null,
        sleepMinutes: hours != null && Number.isFinite(hours) && hours >= 0 && hours <= 24 ? Math.round(hours * 60) : null,
        sleepQuality: inScale(data?.sleep_quality, 3) ? data.sleep_quality : null,
        appetite: inScale(data?.appetite, 5) ? data.appetite : null,
        note: data?.note ?? "",
    }
}

export function wellbeingStepComplete(step: number, draft: WellbeingDraft): boolean {
    if (step === 0) return inScale(draft.wellbeing, 5)
    if (step === 1) return inScale(draft.energy, 5)
    if (step === 2) return inScale(draft.mood, 3) && inScale(draft.stress, 5)
    if (step === 3) return draft.sleepMinutes != null && Number.isInteger(draft.sleepMinutes) && draft.sleepMinutes >= 0 && draft.sleepMinutes <= 1440 && inScale(draft.sleepQuality, 3)
    if (step === 4) return inScale(draft.appetite, 5)
    return step === 5
}

export function wellbeingMonthBounds(month: string) {
    if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(month)) throw new Error("Invalid calendar month")
    const last = new Date(`${month}-01T12:00:00Z`)
    last.setUTCMonth(last.getUTCMonth() + 1)
    return { from: `${month}-01`, to: last.toISOString().slice(0, 10) }
}

/** The diary endpoint caps batches at 200. Split a dense month so earlier days keep their dots. */
export async function loadWellbeingMonth(month: string, read: (from: string, to: string) => Promise<{ entries: CompanionEntry[] }>): Promise<CompanionEntry[]> {
    const { from, to } = wellbeingMonthBounds(month)
    const load = async (start: string, end: string): Promise<CompanionEntry[]> => {
        const result = await read(start, end)
        const days = Math.round((Date.parse(end) - Date.parse(start)) / 86_400_000)
        if (result.entries.length < 200 || days <= 1) return result.entries
        const middle = shiftCalendarDay(start, Math.floor(days / 2))
        const earlier = await load(start, middle)
        return [...earlier, ...await load(middle, end)]
    }
    return load(from, to)
}

/** Retain every historical record; the calendar opens the latest entry for each local day. */
export function wellbeingDays(entries: CompanionEntry[], clock: string, today: string) {
    const days: Record<string, CompanionEntry> = {}
    for (const entry of entries) {
        if (entry.kind !== "wellbeing" || !Number.isFinite(Date.parse(entry.occurred_at))) continue
        const day = companionCalendarDay(entry.occurred_at, clock)
        if (day > today) continue
        const previous = days[day]
        if (!previous || Date.parse(entry.occurred_at) > Date.parse(previous.occurred_at) || entry.occurred_at === previous.occurred_at && entry.id > previous.id) days[day] = entry
    }
    return days
}

export function wellbeingDateLabel(day: string) {
    return mentorDateLabel(new Date(`${day}T12:00:00`), { day: "numeric", month: "long" })
}

export function sleepDurationLabel(minutes: number | null) {
    return minutes == null ? "—" : mt("{0} ч {1} мин", [Math.floor(minutes / 60), minutes % 60])
}

export function appetiteChoice(value: number | null) { return value == null ? null : value < 3 ? 0 : value === 3 ? 1 : 2 }

export function wellbeingSummary(draft: WellbeingDraft): [string, string][] {
    const label = (labels: readonly string[], value: number | null) => value == null ? "—" : mt(labels[value - 1])
    return [
        [mt("Состояние"), label(wellbeingLabels, draft.wellbeing)],
        [mt("Энергия"), draft.energy == null ? "—" : mt("{0} из 5", [draft.energy])],
        [mt("Настроение"), label(moodLabels, draft.mood)],
        [mt("Стресс"), draft.stress == null ? "—" : mt("{0} из 5", [draft.stress])],
        [mt("Сон"), sleepDurationLabel(draft.sleepMinutes)],
        [mt("Насколько выспались?"), label(sleepQualityLabels, draft.sleepQuality)],
        [mt("Аппетит"), draft.appetite == null ? "—" : mt(appetiteLabels[appetiteChoice(draft.appetite)!])],
    ]
}

export function wellbeingSaveAction(draft: WellbeingDraft, day: string, key: string, original?: CompanionEntry, now = new Date()): CompanionAction {
    const today = localDateTime(now).slice(0, 10)
    if (!/^\d{4}-\d{2}-\d{2}$/.test(day) || shiftCalendarDay(day, 0) !== day || day > today) throw new Error(mt("Выберите сегодняшний или прошедший день"))
    if (![0, 1, 2, 3, 4].every(step => wellbeingStepComplete(step, draft))) throw new Error(mt("Заполните все разделы анкеты"))
    if (draft.note.length > Math.max(500, original?.data.note?.length ?? 0)) throw new Error(mt("Сократите заметку до 500 символов"))
    if (original && original.kind !== "wellbeing") throw new Error(mt("Нельзя менять тип существующей записи"))
    // Preserve the exact instant and any older entry metadata when editing.
    const occurred_at = original?.occurred_at ?? (day === today ? now.toISOString() : new Date(`${day}T12:00:00`).toISOString())
    return {
        kind: "entry", request_key: key,
        ...(original ? { resource_id: original.id, expected_version: original.version } : {}),
        entry: { ...original?.data, kind: "wellbeing", occurred_at,
            wellbeing: draft.wellbeing, energy: draft.energy, mood: draft.mood, stress: draft.stress,
            sleep_hours: original?.data.sleep_hours != null && wellbeingDraft(original.data).sleepMinutes === draft.sleepMinutes ? original.data.sleep_hours : Number((draft.sleepMinutes! / 60).toFixed(8)), sleep_quality: draft.sleepQuality,
            appetite: draft.appetite, note: draft.note,
        },
    }
}
