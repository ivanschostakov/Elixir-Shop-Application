const { test } = require("node:test")
const assert = require("node:assert/strict")
const { readFileSync } = require("node:fs")
const { join } = require("node:path")
const loadTs = require("./load-ts.cjs")
const data = loadTs("screens/chat/mentor-data.ts")

test("weekly means use measured values only and never invent a missing baseline", () => {
    const entries = [{ kind: "weight", data: { weight_kg: "80" } }, { kind: "weight", data: { weight_kg: "82" } }, { kind: "weight", data: { weight_kg: null } }, { kind: "wellbeing", data: { energy: 4 } }, { kind: "wellbeing", data: { energy: 2 } }]
    assert.deepEqual(data.recordedMean(entries, "weight", "weight_kg"), { count: 2, value: 81 })
    assert.deepEqual(data.recordedMean(entries, "wellbeing", "energy"), { count: 2, value: 3 })
    assert.deepEqual(data.recordedMean([], "weight", "weight_kg"), { count: 0, value: null })
})

test("planned exercises start without invented actual repetitions or weight", () => {
    const workout = data.startWorkout({ key: "upper", name: "Upper", exercises: [{ key: "press", name: "Press", sets: 3, target_reps: 10, target_weight_kg: "20" }] }, "2026-09-29")
    assert.equal(workout.exercises[0].sets.length, 3)
    assert.deepEqual(workout.exercises[0].sets[0], { weight_kg: null, reps: null, completed: false })
    assert.equal(workout.scheduled_date, "2026-09-29")
    assert.deepEqual(data.workoutTotals(workout), { sets: 0, reps: 0, volume: 0 })
    assert.equal(data.canFinishWorkout(workout), false)
    workout.exercises[0].sets[0] = { weight_kg: "20.5", reps: 8, completed: true }
    workout.exercises[0].sets[1] = { weight_kg: "500", reps: 20, completed: false }
    assert.deepEqual(data.workoutTotals(workout), { sets: 1, reps: 8, volume: 164 })
    assert.equal(data.canFinishWorkout(workout), true, "Partial sessions can finish without fabricating remaining sets")
    workout.exercises[0].sets[0].reps = 1.5
    assert.equal(data.canFinishWorkout(workout), false)
})

test("weight chart uses recorded timestamps, sorts, and handles single or flat values", () => {
    const entry = (id, date, weight) => ({ id, kind: "weight", occurred_at: date, data: { weight_kg: weight } })
    const points = data.chartPoints([entry(2, "2026-09-29T10:00:00Z", "80"), entry(1, "2026-09-20T10:00:00Z", "80"), entry(3, "2026-09-21T10:00:00Z", "invalid")])
    assert.deepEqual(points.map(point => point.id), [1, 2])
    assert.ok(points.every(point => Number.isFinite(point.x) && point.y === 90))
    assert.equal(data.chartPoints([entry(1, "2026-09-29T10:00:00Z", "80")])[0].x, 160)
    assert.deepEqual(data.chartPoints([]), [])
})

test("repeat food keeps confirmed nutrition and estimates but creates a new occurrence", () => {
    const source = { id: 9, version: 3, kind: "meal", data: { kind: "meal", occurred_at: "2026-09-28T10:00:00Z", nutrition: { kcal: "250", protein: "12", fat: "10", carbs: "30" }, name: "Meal", favorite: true, estimated: true, assumptions: "portion estimate" } }
    const result = data.repeatMeal(source, "2026-09-29T10:00:00Z")
    assert.equal(result.occurred_at, "2026-09-29T10:00:00Z")
    assert.equal(result.id, undefined)
    assert.equal(source.data.occurred_at, "2026-09-28T10:00:00Z")
    assert.deepEqual(result.nutrition, source.data.nutrition)
    assert.equal(result.estimated, true)
    assert.throws(() => data.repeatMeal({ kind: "weight" }))
})

test("mentor writes keep the shared integrity, request-key and version contract", async () => {
    const calls = []
    const api = loadTs("services/api/companion.ts", { "@/services/api/client": { apiPost: async (...args) => calls.push(args) }, "@/services/api/ai-chat.constants": { aiChatEndpoint: "/ai-chat" } })
    await api.actCompanion({ kind: "workout_plan", expected_version: 4, workout_plan: null, request_key: "stable-key" })
    await api.actCompanion({ kind: "entry", resource_id: 8, expected_version: 2, entry: { kind: "measurement", occurred_at: "2026-09-29T12:00:00Z", measurement: { waist_cm: "80" } }, request_key: "measurement-key" })
    assert.equal(calls[0][1].expected_version, 4)
    assert.equal(calls[0][1].workout_plan, null)
    assert.equal(calls[1][1].request_key, "measurement-key")
    assert.equal(calls[1][2].appIntegrityAction, "ai-companion")
})

test("mentor preserves native gate and separates real summaries from display samples", () => {
    const mentor = readFileSync(join(__dirname, "../screens/chat/mentor.tsx"), "utf8")
    const chat = readFileSync(join(__dirname, "../screens/chat/chat-screen.tsx"), "utf8")
    const progress = readFileSync(join(__dirname, "../screens/chat/mentor-progress.tsx"), "utf8")
    assert.match(chat, /mentorEnabled = Platform.OS !== "web"/)
    assert.match(chat, /mentorVisible = mentorEnabled && !!companion.mentorPage/)
    assert.match(mentor, /getCompanionSummary/)
    assert.match(progress, /summary\.nutrition\.kcal/)
    assert.match(progress, /summary\.workouts\.completed_sets/)
    assert.match(mentor, /tasks\.filter\(task => task.status === "done"\)\.length/)
    assert.match(mentor, /Фото прогресса\. Не оценивай состав тела/)
    assert.doesNotMatch(mentor, /1240|1900|мышечную массу/)
    assert.match(chat, /MessageAttachmentList/)
})

test("workout receipts are fetched, never guessed; schedule follows the supplied clock", () => {
    const source = readFileSync(join(__dirname, "../screens/chat/mentor-workouts.tsx"), "utf8")
    assert.doesNotMatch(source, /version: saved.version \+ 1/)
    assert.match(source, /getCompanionEntries\(day, shiftCalendarDay\(day, 1\), "workout"\)/)
    assert.match(source, /index !== weekday/)
    const time = loadTs("screens/chat/companion-timezones.ts")
    assert.equal(time.companionCalendarDay("2026-09-29T23:00:00Z", "Asia/Tokyo|0|2026-09-30"), "2026-09-30")
    assert.equal(time.companionCalendarDay("2026-09-29T23:00:00Z", "UTC-03:30|0|2026-09-29"), "2026-09-29")
    assert.equal(time.shiftCalendarDay("2026-09-30", 1), "2026-10-01")
})

test("saved private photos and all-time favorites use separate authenticated read endpoints", async () => {
    const calls = []
    const api = loadTs("services/api/companion.ts", { "@/services/api/client": { apiGet: async (...args) => calls.push(args) }, "@/services/api/ai-chat.constants": { aiChatEndpoint: "/ai-chat" } })
    await api.getCompanionProgressPhotos("2026-09-01", "2026-09-30")
    await api.getCompanionFavoriteMeals()
    assert.equal(calls[0][0], "/ai-chat/companion/progress-photos")
    assert.equal(calls[0][2].appIntegrityAction, "ai-companion")
    assert.equal(calls[1][0], "/ai-chat/companion/favorite-meals")
    assert.equal(calls[1][1], undefined)
    const source = readFileSync(join(__dirname, "../screens/chat/mentor-photos.tsx"), "utf8")
    assert.match(source, /message.sender === "user"/)
    assert.match(source, /attachment.is_private/)
    assert.match(source, /photo_attachments/)
    assert.match(source, /kind: "progress_photo"/)
    assert.doesNotMatch(source, /\/media\//)
})
