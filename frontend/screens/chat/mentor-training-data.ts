import { mentorText as mt } from "@/i18n/mentor-translations"
import { companionCalendarDay, shiftCalendarDay } from "@/screens/chat/companion-timezones"
import { numeric, startWorkout } from "@/screens/chat/mentor-data"
import type { CompanionEntry, Workout, WorkoutPlan, WorkoutTargets } from "@/services/api/companion"

export const trainingWeekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"] as const
export const trainingDayNames = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"] as const
export const trainingGoals = { muscle: "Набрать мышцы", strength: "Стать сильнее", endurance: "Выносливость", maintain: "Поддерживать форму" } as const
export const trainingExperiences = { beginner: "Новичок", some: "Есть опыт", advanced: "Опытный" } as const
export const trainingPlaces = { gym: "Зал", home: "Дома", outdoors: "Улица" } as const
export const trainingEquipment = { dumbbells: "Гантели", barbell: "Штанга", machines: "Тренажёры", bands: "Резинки", pullup: "Турник", bodyweight: "Свой вес" } as const

export const trainingWeekday = (day: string) => (new Date(`${day}T12:00:00Z`).getUTCDay() + 6) % 7
export const trainingWeek = (day: string) => Array.from({ length: 7 }, (_, index) => shiftCalendarDay(day, index - trainingWeekday(day)))
export const scheduledTraining = (plan: WorkoutPlan | null | undefined, day: string) => plan && day >= plan.start_date && (!plan.end_date || day <= plan.end_date) ? plan.days.filter(item => item.weekdays.includes(trainingWeekday(day))) : []
export const trainingRepLabel = (exercise: Partial<WorkoutTargets> & { sets?: number | unknown[]; target_sets?: number | null }) => {
    const sets = exercise.target_sets ?? (typeof exercise.sets === "number" ? exercise.sets : undefined)
    const reps = exercise.target_reps == null ? "—" : exercise.target_reps_max && exercise.target_reps_max !== exercise.target_reps ? `${exercise.target_reps}–${exercise.target_reps_max}` : String(exercise.target_reps)
    return `${sets ?? "—"} × ${reps}`
}

export function validateTrainingPlan(plan: WorkoutPlan): string | null {
    const validDate = (value: string) => { try { return /^\d{4}-\d{2}-\d{2}$/.test(value) && shiftCalendarDay(value, 0) === value } catch { return false } }
    if (!plan.name.trim() || plan.name.length > 200 || !validDate(plan.start_date) || plan.end_date && (!validDate(plan.end_date) || plan.end_date < plan.start_date)) return mt("Проверьте название и даты программы")
    if (!plan.days.length || plan.days.length > 14 || new Set(plan.days.map(day => day.key)).size !== plan.days.length) return mt("Добавьте тренировочные дни")
    for (const day of plan.days) {
        if (!day.key || day.key.length > 80 || !day.name.trim() || day.name.length > 200 || !day.weekdays.length || new Set(day.weekdays).size !== day.weekdays.length || day.weekdays.some(value => !Number.isInteger(value) || value < 0 || value > 6) || day.duration_minutes != null && (!Number.isInteger(day.duration_minutes) || day.duration_minutes < 1 || day.duration_minutes > 300)) return mt("Проверьте расписание тренировок")
        if (!day.exercises.length || day.exercises.length > 30 || new Set(day.exercises.map(exercise => exercise.key)).size !== day.exercises.length) return mt("Добавьте упражнения в каждый тренировочный день")
        for (const exercise of day.exercises) {
            if (!exercise.key || exercise.key.length > 80 || !exercise.name.trim() || exercise.name.length > 200 || !Number.isInteger(exercise.sets) || exercise.sets < 1 || exercise.sets > 30 || exercise.target_reps != null && (!Number.isInteger(exercise.target_reps) || exercise.target_reps < 1 || exercise.target_reps > 1000) || exercise.target_reps_max != null && (exercise.target_reps == null || !Number.isInteger(exercise.target_reps_max) || exercise.target_reps_max < exercise.target_reps || exercise.target_reps_max > 1000) || exercise.target_weight_kg != null && (numeric(exercise.target_weight_kg) == null || Number(exercise.target_weight_kg) < 0 || Number(exercise.target_weight_kg) > 1000) || exercise.rest_seconds != null && (!Number.isInteger(exercise.rest_seconds) || exercise.rest_seconds < 0 || exercise.rest_seconds > 1800)) return mt("Проверьте упражнения, подходы и повторения")
        }
    }
    return null
}

export function mergeTrainingEntries(...groups: CompanionEntry[][]): CompanionEntry[] {
    const entries = new Map<number, CompanionEntry>()
    for (const group of groups) for (const entry of group) if (entry.kind === "workout" && entry.data.workout && (entries.get(entry.id)?.version ?? -1) <= entry.version) entries.set(entry.id, entry)
    return [...entries.values()].sort((a, b) => Date.parse(b.occurred_at) - Date.parse(a.occurred_at) || b.id - a.id)
}

export const trainingEntryDay = (entry: CompanionEntry, clock: string) => entry.data.workout?.scheduled_date ?? companionCalendarDay(entry.occurred_at, clock)
export function lastTrainingWeight(exercise: { key: string; name: string }, entries: CompanionEntry[], before: string) {
    const name = exercise.name.trim().toLocaleLowerCase()
    for (const entry of entries) {
        if (Date.parse(entry.occurred_at) >= Date.parse(before) || entry.data.workout?.status !== "completed") continue
        const item = entry.data.workout.exercises.find(item => item.name.trim().toLocaleLowerCase() === name)
        const actual = item?.sets.filter(set => set.completed && set.weight_kg != null).at(-1)
        if (actual) return actual.weight_kg
    }
    return null
}

export function beginTraining(day: WorkoutPlan["days"][number], date: string, instant: string): Workout {
    const workout = startWorkout(day, date)
    return { ...workout, timer_started_at: instant, rest_ends_at: null, exercises: workout.exercises.map((exercise, index) => ({ ...exercise, target_sets: day.exercises[index].sets, target_reps: day.exercises[index].target_reps, target_reps_max: day.exercises[index].target_reps_max, target_weight_kg: day.exercises[index].target_weight_kg, rest_seconds: day.exercises[index].rest_seconds })) }
}

type DraftSet = { weight: string; reps: string; completed: boolean }
export type TrainingSessionDraft = Omit<Workout, "exercises"> & { exercises: (Omit<Workout["exercises"][number], "sets"> & { sets: DraftSet[] })[] }
export function trainingSessionDraft(workout: Workout): TrainingSessionDraft {
    return { ...workout, exercises: workout.exercises.map(exercise => ({ ...exercise, sets: exercise.sets.map(set => ({ weight: set.weight_kg == null ? "" : String(set.weight_kg), reps: set.reps == null ? "" : String(set.reps), completed: set.completed })) })) }
}
export function trainingSessionPayload(draft: TrainingSessionDraft): Workout {
    return { ...draft, exercises: draft.exercises.map(exercise => ({ ...exercise, sets: exercise.sets.map(set => {
        const weight = numeric(set.weight), reps = numeric(set.reps)
        if (set.weight.trim() && (weight == null || weight < 0 || weight > 1000) || set.reps.trim() && (reps == null || !Number.isInteger(reps) || reps < 1 || reps > 1000) || set.completed && (weight == null || reps == null)) throw new Error(mt("Укажите вес от 0 до 1000 кг и целое число повторений от 1 до 1000"))
        return { weight_kg: weight, reps, completed: set.completed }
    }) })) }
}
export const trainingElapsed = (workout: Pick<Workout, "duration_seconds" | "timer_started_at" | "paused_at" | "status">, now: number) => workout.status === "completed" || !workout.timer_started_at ? workout.duration_seconds : Math.min(86400, Math.max(workout.duration_seconds, Math.floor(((workout.paused_at ? Date.parse(workout.paused_at) : now) - Date.parse(workout.timer_started_at)) / 1000) || 0))
export const trainingRest = (workout: Pick<Workout, "rest_ends_at" | "paused_at">, now: number) => Math.max(0, Math.ceil((Date.parse(workout.rest_ends_at ?? "") - (workout.paused_at ? Date.parse(workout.paused_at) : now)) / 1000) || 0)

export function pauseTraining<T extends Workout | TrainingSessionDraft>(workout: T, now: number): T {
    if (workout.status !== "in_progress" || workout.paused_at) return workout
    return { ...workout, duration_seconds: trainingElapsed(workout, now), paused_at: new Date(now).toISOString() }
}
export function resumeTraining<T extends Workout | TrainingSessionDraft>(workout: T, now: number): T {
    if (workout.status !== "in_progress" || !workout.paused_at) return workout
    const elapsed = trainingElapsed(workout, now), gap = Math.max(0, now - Date.parse(workout.paused_at))
    const started = Date.parse(workout.timer_started_at ?? ""), rest = Date.parse(workout.rest_ends_at ?? "")
    return { ...workout, paused_at: null, duration_seconds: elapsed,
        timer_started_at: new Date(Number.isFinite(started) ? started + gap : now - elapsed * 1000).toISOString(),
        rest_ends_at: trainingRest(workout, now) > 0 ? new Date(rest + gap).toISOString() : null }
}
export const trainingTimer = (seconds: number) => `${String(Math.floor(Math.max(0, seconds) / 60)).padStart(2, "0")}:${String(Math.floor(Math.max(0, seconds)) % 60).padStart(2, "0")}`
