import type { CompanionEntry, Workout, WorkoutPlan } from "@/services/api/companion"

export type MentorPage = "today" | "nutrition" | "workouts" | "course" | "progress" | "more" | "adjust"
export const measurementLabels = { waist_cm: "Талия, см", chest_cm: "Грудь, см", hips_cm: "Бёдра, см", arm_cm: "Рука, см", thigh_cm: "Бедро, см", body_fat_percent: "Жир, % (измеренный)" }
export const goalLabels = { weight_loss: "Снижение веса", weight_gain: "Набор веса", maintain: "Поддержание", custom: "Своя цель", course: "Сопровождение курса" }
export function numeric(value: unknown): number | null {
    if (value == null || String(value).trim() === "") return null
    const number = Number(String(value).replace(",", "."))
    return Number.isFinite(number) ? number : null
}
export function recordedMean(entries: CompanionEntry[], kind: "weight" | "wellbeing", field: "weight_kg" | "energy") {
    const values = entries.filter(entry => entry.kind === kind).map(entry => numeric(entry.data[field])).filter((value): value is number => value !== null)
    return { count: values.length, value: values.length ? Math.round(values.reduce((sum, value) => sum + value, 0) / values.length * 100) / 100 : null }
}
export function weightPoints(entries: CompanionEntry[]) {
    return entries.filter(entry => entry.kind === "weight" && numeric(entry.data.weight_kg) !== null)
        .sort((a, b) => Date.parse(a.occurred_at) - Date.parse(b.occurred_at))
        .map(entry => ({ id: entry.id, time: Date.parse(entry.occurred_at), value: Number(entry.data.weight_kg), date: entry.occurred_at }))
}
export function chartPoints(entries: CompanionEntry[], width = 320, height = 180) {
    const points = weightPoints(entries)
    if (!points.length) return []
    const values = points.map(point => point.value)
    const min = Math.min(...values), max = Math.max(...values)
    const first = points[0].time, last = points[points.length - 1].time
    return points.map(point => ({ ...point, x: last === first ? width / 2 : 28 + (point.time - first) / (last - first) * (width - 56), y: max === min ? height / 2 : 20 + (max - point.value) / (max - min) * (height - 40) }))
}
export function workoutTotals(workout: Workout) {
    const sets = workout.exercises.flatMap(exercise => exercise.sets).filter(set => set.completed)
    return { sets: sets.length, reps: sets.reduce((sum, set) => sum + (set.reps ?? 0), 0), volume: sets.reduce((sum, set) => sum + Number(set.weight_kg ?? 0) * (set.reps ?? 0), 0) }
}
export function startWorkout(day: WorkoutPlan["days"][number], date: string): Workout {
    return { name: day.name, plan_day_key: day.key, scheduled_date: date, status: "in_progress", duration_seconds: 0, current_exercise_index: 0,
        exercises: day.exercises.map(exercise => ({ key: exercise.key, name: exercise.name, sets: Array.from({ length: exercise.sets }, () => ({ weight_kg: null, reps: null, completed: false })) })) }
}
export function canFinishWorkout(workout: Workout) {
    const completed = workout.exercises.flatMap(exercise => exercise.sets).filter(set => set.completed)
    return completed.length > 0 && completed.every(set => numeric(set.weight_kg) !== null && Number(set.weight_kg) >= 0 && Number.isInteger(set.reps) && Number(set.reps) > 0)
}
export function repeatMeal(entry: CompanionEntry, now = new Date().toISOString()) {
    if (entry.kind !== "meal") throw new Error("Можно повторить только приём пищи")
    return { ...entry.data, occurred_at: now, favorite: false }
}
