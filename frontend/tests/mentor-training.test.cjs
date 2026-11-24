const { test } = require("node:test")
const assert = require("node:assert/strict")
const load = require("./load-ts.cjs")
load("i18n/translations.ts").setTranslationLanguage("ru")
const dates = load("screens/chat/companion-timezones.ts"), old = load("screens/chat/mentor-data.ts")
const data = load("screens/chat/mentor-training-data.ts", { "@/screens/chat/companion-timezones": dates, "@/screens/chat/mentor-data": old })
const home = load("screens/chat/mentor-home-data.ts", { "@/screens/chat/companion-timezones": dates, "@/screens/chat/mentor-data": old })
const plan = () => ({ name: "Strength", start_date: "2026-11-23", end_date: null, days: [{ key: "mon", name: "Upper", weekdays: [0], duration_minutes: 45, exercises: [{ key: "bench", name: "Bench press", sets: 3, target_reps: 8, target_reps_max: 12, target_weight_kg: null, rest_seconds: 90 }, { key: "row", name: "Row", sets: 2, target_reps: 10, target_weight_kg: null }] }] })
const entry = (id, workout, time = "2026-11-23T12:00:00Z", version = 1) => ({ id, version, kind: "workout", occurred_at: time, data: { kind: "workout", occurred_at: time, workout } })
const state = () => ({ available: true, as_of: "2026-11-23T12:00:00Z", received_at: Date.now(), entries: [], profile: { id: 1, enabled: true, version: 4, data: {}, settings: { timezone: "UTC" } } })
const nodes = tree => !tree || typeof tree !== "object" ? [] : Array.isArray(tree) ? tree.flatMap(nodes) : [tree, ...nodes(tree.props?.children), ...nodes(tree.props?.footer)]
const flush = async () => { for (let i = 0; i < 30; i++) await Promise.resolve() }

test("schedule respects calendar boundaries and rejects malformed dates without throwing", () => {
    assert.deepEqual(data.trainingWeek("2026-11-29"), ["2026-11-23", "2026-11-24", "2026-11-25", "2026-11-26", "2026-11-27", "2026-11-28", "2026-11-29"])
    assert.equal(data.scheduledTraining(plan(), "2026-11-23").length, 1)
    assert.equal(data.scheduledTraining(plan(), "2026-11-16").length, 0)
    assert.equal(data.scheduledTraining({ ...plan(), end_date: "2026-11-29" }, "2026-11-30").length, 0)
    for (const patch of [{ start_date: "bad" }, { end_date: "bad" }, { end_date: "2026-02-30" }, { end_date: "2026-11-22" }]) assert.ok(data.validateTrainingPlan({ ...plan(), ...patch }))
    assert.equal(data.validateTrainingPlan(plan()), null)
    const bad = plan(); bad.days[0].exercises[0].target_reps_max = 6; assert.ok(data.validateTrainingPlan(bad))
})

test("new sessions snapshot targets without filling actual values; later plan edits preserve history", () => {
    const p = plan(), workout = data.beginTraining(p.days[0], "2026-11-23", "2026-11-23T12:00:00Z")
    assert.equal(workout.exercises[0].target_reps_max, 12); assert.equal(workout.exercises[0].rest_seconds, 90)
    assert.deepEqual(workout.exercises[0].sets[0], { weight_kg: null, reps: null, completed: false })
    p.days[0].exercises[0].target_reps = 20; assert.equal(workout.exercises[0].target_reps, 8)
    assert.equal(data.trainingRepLabel(workout.exercises[0]), "3 × 8–12")
    assert.equal(data.trainingElapsed(workout, Date.parse("2026-11-23T12:02:03Z")), 123)
    assert.equal(data.trainingTimer(123.5), "02:03")
    const draft = data.trainingSessionDraft(workout)
    draft.exercises[0].sets[0] = { weight: "0", reps: "12", completed: true }
    draft.exercises[0].sets[1] = { weight: "12,5", reps: "8", completed: false }
    const result = data.trainingSessionPayload(draft)
    assert.equal(result.exercises[0].sets[1].weight_kg, 12.5); assert.deepEqual(old.workoutTotals(result), { sets: 1, reps: 12, volume: 0 })
    for (const patch of [{ weight: "" }, { reps: "" }, { reps: "8.5" }, { weight: "-1" }, { weight: "1001" }]) {
        const invalid = structuredClone(draft); Object.assign(invalid.exercises[0].sets[0], patch); assert.throws(() => data.trainingSessionPayload(invalid))
    }
})

test("last weights use earlier completed sets, compare offset timestamps as instants and merge latest versions", () => {
    const workout = data.beginTraining(plan().days[0], "2026-11-23", "2026-11-23T12:00:00Z")
    workout.status = "completed"; workout.exercises[0].sets = [{ weight_kg: 35, reps: 8, completed: true }, { weight_kg: 99, reps: 8, completed: false }]
    const before = entry(1, workout, "2026-11-23T11:00:00Z"), future = entry(2, workout, "2026-11-23T05:30:00-07:00"), newer = { ...before, version: 2 }
    const merged = data.mergeTrainingEntries([newer], [before, future]); assert.equal(merged.find(row => row.id === 1), newer)
    assert.equal(data.lastTrainingWeight({ key: "new-key", name: "Bench press" }, merged, "2026-11-23T12:00:00Z"), 35)
    assert.equal(data.lastTrainingWeight({ key: "bench", name: "Squat" }, merged, "2026-11-23T12:00:00Z"), null, "AI keys can be reused in another plan; they do not identify an exercise globally")
    assert.equal(data.lastTrainingWeight({ key: "bench", name: "Bench press" }, [{ ...before, data: { workout: { ...workout, status: "in_progress" } } }], "2026-11-23T12:00:00Z"), null)
})

function harness(file, overrides = {}, controller = { state: state(), clock: "UTC|0|2026-11-23", busy: false }) {
    const slots = [], effects = [], alerts = [], calls = { saved: [], closed: 0, updated: [] }
    let cursor = 0, sequence = 0, fail = false
    const react = {
        useState(initial) { const i = cursor++; if (!(i in slots)) slots[i] = typeof initial === "function" ? initial() : initial; return [slots[i], next => { slots[i] = typeof next === "function" ? next(slots[i]) : next }] },
        useRef(initial) { const i = cursor++; return slots[i] ??= { current: initial } },
        useEffect(fn, deps) { const i = cursor++; if (!slots[i] || !deps || deps.some((value, j) => value !== slots[i].deps[j])) effects.push(() => { slots[i]?.cleanup?.(); slots[i] = { deps, cleanup: fn() } }) },
    }
    const jsx = (type, props) => ({ type, props: type === "Transition" ? { ...props, children: props.render(props.step) } : props })
    controller.perform ??= async action => {
        calls.saved.push(action); if (fail) throw Error("Connection lost")
        if (action.kind === "workout_plan") { controller.state = { ...controller.state, profile: { ...controller.state.profile, version: controller.state.profile.version + 1, data: { workout_plan: action.workout_plan } } }; return controller.state }
        const previous = controller.state.entries.find(item => item.id === action.resource_id)
        const saved = entry(previous?.id ?? 10, action.entry.workout, action.entry.occurred_at, (previous?.version ?? 0) + 1)
        controller.state = { ...controller.state, entries: [...controller.state.entries.filter(item => item.id !== saved.id), saved] }; return controller.state
    }
    const module = load(file, {
        react, "react/jsx-runtime": { jsx, jsxs: jsx, Fragment: "Fragment" },
        "react-native": { Alert: { alert: (...args) => alerts.push(args) }, Image: "Image", Modal: "Modal", Pressable: "Button", ScrollView: "Scroll", Text: "Text", View: "View" },
        "expo-image-picker": { launchImageLibraryAsync: async () => ({ canceled: false, assets: [{ uri: "private-photo.jpg" }] }) },
        "@/components/platform/app-step-transition": { AppStepTransition: "Transition" },
        "@/components/platform/app-form-layout": { AppFormLayout: "Form" },
        "@/screens/chat/mentor-home": { MentorHomeHeader: "Header" },
        "@/providers/language-provider": { useLanguage: () => ({ language: "ru" }) },
        "@/screens/chat/mentor-ui": { useMentorPalette: () => ({}) },
        "@/screens/chat/companion-consent": { CompanionActionCancelled: class extends Error {} },
        "@/services/api/ai-data-consent": { AiConsentDeclinedError: class extends Error {} },
        "@/screens/chat/chat-attachments": { createAttachmentFromImagePickerAsset: asset => ({ ...asset, fileName: "photo.jpg", mimeType: "image/jpeg" }) },
        "@/services/api/companion": { requestKey: () => `workout-request-${++sequence}`, getCompanionEntries: async () => ({ entries: controller.state.entries }) },
        "@/services/api/companion-workouts": { requestWorkoutDraft: async () => ({ plan: plan(), message: "Ready", questions: [] }), getWorkoutLibrary: async () => ({ entries: [] }) },
        "@/screens/chat/mentor-training-data": data,
        "@/screens/chat/mentor-training-ui": { TrainingAction: "Action", TrainingChoice: "Choice", TrainingDurationPicker: "DurationPicker", TrainingField: "Field", TrainingFrame: "Frame", TrainingHeading: "Heading", TrainingIcon: "Icon", trainingStyles: {} },
        "@/screens/chat/mentor-training-plan": { MentorTrainingPlan: "Planner" },
        "@/screens/chat/mentor-training-session": { MentorTrainingSession: "Session" },
        "@/screens/chat/mentor-data": old, "@/screens/chat/mentor-home-data": home, "@/screens/chat/companion-timezones": dates,
        "@/utils/errors": { getErrorMessage: failure => failure.message }, ...overrides,
    })
    const props = { controller, onClose: () => calls.closed++, onSaved: () => calls.closed++, onUpdated: row => calls.updated.push(row) }
    const render = extra => { cursor = 0; const tree = Object.values(module)[0]({ ...props, ...extra }); effects.splice(0).forEach(fn => fn()); return tree }
    const find = (type, label, extra) => nodes(render(extra)).find(node => node.type === type && (!label || node.props.label === label || node.props.accessibilityLabel === label))
    return { controller, calls, alerts, render, find, fail(value = true) { fail = value }, cleanup() { slots.forEach(slot => slot?.cleanup?.()) } }
}

function fillSetup(h) {
    const p = { mode: "generate", today: "2026-11-23" }
    const tap = (type, label) => h.find(type, label, p).props.onPress()
    tap("Choice", "Набрать мышцы"); tap("Choice", "Новичок"); tap("Action", "Далее")
    tap("Choice", "Зал"); tap("Choice", "Гантели"); tap("Action", "Далее")
    tap("Choice", "Пн"); h.find("DurationPicker", null, p).props.onChange(95); tap("Action", "Далее"); tap("Action", "Далее")
}

test("questionnaire photos are optional; Skip omits selected images and a draft never auto-saves", async t => {
    const requests = [], p = { mode: "generate", today: "2026-11-23" }
    const h = harness("screens/chat/mentor-training-plan.tsx", { "@/services/api/companion-workouts": { requestWorkoutDraft: async (...args) => { requests.push(args); return { plan: plan(), message: "Ready", questions: [] } } } }); t.after(h.cleanup)
    fillSetup(h); h.find("Button", "Фото спереди", p).props.onPress(); await flush()
    assert.ok(nodes(h.render(p)).some(node => node.type === "Image"))
    h.find("Action", "Пропустить", p).props.onPress(); await flush()
    assert.equal(requests.length, 1); assert.deepEqual(requests[0][1], []); assert.deepEqual(requests[0][0].setup.weekdays, [0]); assert.equal(requests[0][0].setup.minutes, 95); assert.equal(h.calls.saved.length, 0)
    h.find("Action", "Сохранить план", p).props.onPress(); await flush()
    assert.equal(h.calls.saved[0].kind, "workout_plan"); assert.equal(h.calls.closed, 1)
})

test("import retries the same key, asks for missing details and blocks remote plan overwrites", async t => {
    const requests = []; let fail = true
    const h = harness("screens/chat/mentor-training-plan.tsx", { "@/services/api/companion-workouts": { requestWorkoutDraft: async (...args) => { requests.push(args); if (fail) throw Error("Connection lost"); return requests.length < 3 ? { plan: null, message: "Need days", questions: ["Which days?"] } : { plan: plan(), message: "Ready", questions: [] } } } }); t.after(h.cleanup)
    const p = { mode: "import", today: "2026-11-23" }
    h.find("Field", "Ваша программа", p).props.onChange("Bench press 3×8")
    h.find("Action", "Разобрать программу", p).props.onPress(); await flush(); fail = false
    h.find("Action", "Разобрать программу", p).props.onPress(); await flush()
    assert.equal(requests[0][2], requests[1][2]); assert.equal(h.find("Action", "Сохранить план", p), undefined)
    h.find("Field", "Уточните программу", p).props.onChange("Monday"); h.find("Action", "Продолжить", p).props.onPress(); await flush()
    assert.match(requests[2][0].text, /Bench press.*\nWhich days\?\nMonday/); assert.notEqual(requests[1][2], requests[2][2]); assert.equal(h.calls.saved.length, 0)
    h.controller.state.profile.data.workout_plan = { ...plan(), name: "Changed elsewhere" }
    h.find("Action", "Сохранить план", p).props.onPress(); await flush(); assert.equal(h.calls.saved.length, 0)
    assert.ok(h.alerts.some(([, message]) => message.includes("другом устройстве")))
})

test("set logging requires actuals, ignores double taps and retries an identical versioned action", async t => {
    const initial = entry(12, data.beginTraining(plan().days[0], "2026-11-23", "2026-11-23T12:00:00Z"), undefined, 3)
    const h = harness("screens/chat/mentor-training-session.tsx"); t.after(h.cleanup); h.controller.state.entries = [initial]
    const p = { entry: initial }
    h.find("Button", "Подход 1 выполнен", p).props.onPress(); await flush(); assert.equal(h.calls.saved.length, 0)
    assert.match(h.alerts.at(-1)[1], /от 0 до 1000 кг/)
    h.find("Field", "Вес в подходе 1", p).props.onChange("100"); h.find("Field", "Повторения в подходе 1", p).props.onChange("1500")
    h.find("Button", "Подход 1 выполнен", p).props.onPress(); await flush()
    assert.equal(h.calls.saved.length, 0); assert.match(h.alerts.at(-1)[1], /от 1 до 1000/)
    const footer = nodes(h.render(p)).find(node => node.type === "Frame").props.footer
    assert.equal(nodes(footer).some(node => node.type === "View"), false, "native alerts do not reserve footer space")
    h.find("Field", "Вес в подходе 1", p).props.onChange("32,5"); h.find("Field", "Повторения в подходе 1", p).props.onChange("8")
    h.fail(); const check = h.find("Button", "Подход 1 выполнен", p); check.props.onPress(); check.props.onPress(); await flush()
    assert.equal(h.calls.saved.length, 1); assert.equal(h.calls.saved[0].expected_version, 3)
    assert.equal(h.alerts.at(-1)[1], "Connection lost")
    assert.equal(h.calls.saved[0].entry.workout.exercises[0].sets[0].weight_kg, 32.5); assert.equal(h.calls.saved[0].entry.workout.exercises[0].sets[1].completed, false)
    h.fail(false); h.find("Action", "Повторить сохранение", p).props.onPress(); await flush()
    assert.strictEqual(h.calls.saved[0], h.calls.saved[1]); assert.equal(h.calls.updated[0].version, 4)
    h.find("Action", "Следующее упражнение", p).props.onPress(); await flush(); assert.equal(h.calls.saved.at(-1).expected_version, 4)
    assert.equal(h.calls.saved.at(-1).entry.workout.current_exercise_index, 1)
})

test("Back persists typed unfinished sets and Finish rejects zero completed work", async t => {
    const initial = entry(12, data.beginTraining(plan().days[0], "2026-11-23", "2026-11-23T12:00:00Z"))
    const h = harness("screens/chat/mentor-training-session.tsx"); t.after(h.cleanup); h.controller.state.entries = [initial]
    const p = { entry: initial }
    h.find("Action", "Завершить тренировку", p).props.onPress(); assert.match(h.alerts.at(-1)[1], /хотя бы один выполненный подход/)
    h.find("Field", "Вес в подходе 1", p).props.onChange("20"); nodes(h.render(p)).find(node => node.type === "Frame").props.onBack(); await flush()
    assert.equal(h.calls.saved.length, 1); assert.equal(h.calls.closed, 1)
    assert.equal(h.calls.saved[0].entry.workout.exercises[0].sets[0].weight_kg, 20); assert.equal(h.calls.saved[0].entry.workout.exercises[0].sets[0].completed, false)
})

test("main tab loads history before starting, starts once and resumes old sessions after a plan change", async t => {
    const c = { state: state(), clock: "UTC|0|2026-11-23", busy: false }; c.state.profile.data.workout_plan = plan()
    let resolve; const h = harness("screens/chat/mentor-training.tsx", { "@/services/api/companion-workouts": { getWorkoutLibrary: () => new Promise(done => { resolve = done }) } }, c); t.after(h.cleanup)
    const p = { active: true, onSettings() {} }; assert.equal(h.find("Action", "Начать тренировку", p).props.disabled, true)
    resolve({ entries: [] }); await flush(); const start = h.find("Action", "Начать тренировку", p); assert.equal(start.props.disabled, false)
    start.props.onPress(); start.props.onPress(); await flush(); assert.equal(h.calls.saved.length, 1); assert.ok(nodes(h.render(p)).some(node => node.type === "Session"))
    const running = entry(77, { ...data.beginTraining(plan().days[0], "2026-11-16", "2026-11-16T12:00:00Z"), name: "Previous program" }, "2026-11-16T12:00:00Z")
    const other = harness("screens/chat/mentor-training.tsx", { "@/services/api/companion-workouts": { getWorkoutLibrary: async () => ({ entries: [running] }) } }, { state: { ...c.state, entries: [] }, clock: c.clock, busy: false }); t.after(other.cleanup)
    other.render(p); await flush(); other.find("Action", "Продолжить тренировку", p).props.onPress()
    assert.equal(nodes(other.render(p)).find(node => node.type === "Session").props.entry.id, 77)
})

test("AI drafts require consent and upload a private multipart preview through the integrity-protected API", async () => {
    const original = global.FormData, calls = []; let accepted = true
    global.FormData = class { constructor() { this.fields = [] } append(...field) { this.fields.push(field) } }
    try {
        const api = load("services/api/companion-workouts.ts", {
            "@/services/api/client": { apiGet: async (...args) => calls.push(["read", ...args]), apiPostMultipart: async (...args) => { calls.push(["upload", ...args]); return { plan: null, message: "Which days?", questions: ["Which days?"] } } },
            "@/services/api/ai-chat.constants": { aiChatEndpoint: "/users/me/ai-chat" },
            "@/services/api/ai-data-consent": { ensureAiDataConsent: async () => { calls.push(["consent"]); if (!accepted) throw Error("Declined") } },
        })
        const payload = { mode: "import", language: "ru", start_date: "2026-11-23", text: "Bench 3×8" }
        await api.requestWorkoutDraft(payload, [{ uri: "file:///private-training.jpg", fileName: "front.jpg", mimeType: "image/jpeg" }], "workout-key-1")
        assert.equal(calls[0][0], "consent")
        const [, url, form, options] = calls[1]; assert.equal(url, "/users/me/ai-chat/companion/workout-draft")
        assert.equal(options.appIntegrityAction, "ai-companion")
        assert.deepEqual(form.fields, [["payload", JSON.stringify(payload)], ["client_request_id", "workout-key-1"], ["attachments", { uri: "file:///private-training.jpg", name: "front.jpg", type: "image/jpeg" }]])
        accepted = false; await assert.rejects(api.requestWorkoutDraft(payload, [], "workout-key-2"), /Declined/)
        assert.equal(calls.filter(call => call[0] === "upload").length, 1)
        await api.getWorkoutLibrary("2026-11-23", "2026-11-30")
        assert.deepEqual(calls.at(-1), ["read", "/users/me/ai-chat/companion/workouts", { from_date: "2026-11-23", to_date: "2026-11-30" }, { appIntegrityAction: "ai-companion" }])
    } finally { global.FormData = original }
})


test("history read failures show one native alert and retain an explicit retry without inline error space", async t => {
    let fail = true, reads = 0
    const c = { state: state(), clock: "UTC|0|2026-11-23", busy: false }; c.state.profile.data.workout_plan = plan()
    const h = harness("screens/chat/mentor-training.tsx", { "@/services/api/companion-workouts": { getWorkoutLibrary: async () => { reads++; if (fail) throw Error("History unavailable"); return { entries: [] } } } }, c); t.after(h.cleanup)
    const p = { active: true, onSettings() {} }
    h.render(p); await flush(); h.render(p); h.render(p)
    assert.deepEqual(h.alerts, [["Тренировки", "History unavailable"]]); assert.equal(reads, 1)
    assert.equal(nodes(h.render(p)).some(node => node.props.accessibilityRole === "alert"), false)
    assert.equal(h.find("Action", "Начать тренировку", p).props.disabled, true)
    fail = false; h.find("Action", "Повторить загрузку", p).props.onPress(); h.render(p); await flush()
    assert.equal(h.find("Action", "Начать тренировку", p).props.disabled, false); assert.equal(reads, 2)
})


test("native duration wheels select individual hours and minutes within limits and retain optional empty durations", () => {
    const jsx = (type, props) => ({ type, props })
    const Picker = Object.assign(function Picker() {}, { Item: "PickerItem" })
    const { TrainingDurationPicker } = load("screens/chat/mentor-training-ui.tsx", {
        "react/jsx-runtime": { jsx, jsxs: jsx, Fragment: "Fragment" },
        "react-native": { Platform: { OS: "ios" }, View: "View", StyleSheet: { create: value => value, hairlineWidth: 0.5 } },
        "@react-native-picker/picker": { Picker },
        "react-native-safe-area-context": {},
        "@/screens/chat/mentor-home": {},
        "@/screens/chat/mentor-ui": { useMentorPalette: () => ({ text: "#202923", input: "#ECEEF0" }) },
        ...Object.fromEntries(["check", "dumbbell", "pencil-line", "camera", "x", "chevron-left", "chevron-right"].map(icon => [`@/assets/icons/mentor/${icon}.svg`, "Icon"])),
    })
    let minutes = 45
    const wheels = (extra = {}) => nodes(TrainingDurationPicker({ minutes, onChange: value => { minutes = value }, ...extra })).filter(node => node.type === Picker)
    wheels()[1].props.onValueChange(37); assert.equal(minutes, 37)
    wheels()[0].props.onValueChange(1); assert.equal(minutes, 97)
    wheels()[0].props.onValueChange(3); assert.equal(minutes, 180)
    assert.deepEqual(nodes(wheels()[1]).filter(node => node.type === "PickerItem").map(node => node.props.value), [0])
    wheels()[0].props.onValueChange(0); assert.equal(minutes, 15)
    assert.equal(nodes(wheels()[1]).find(node => node.type === "PickerItem").props.value, 15)
    wheels()[1].props.onValueChange(0); assert.equal(minutes, 15, "a delayed native event cannot select an invalid duration")
    minutes = null
    const optional = { optional: true, minMinutes: 1, maxMinutes: 300 }
    assert.equal(wheels(optional)[0].props.selectedValue, -1); assert.equal(wheels(optional)[1].props.enabled, false)
    wheels(optional)[0].props.onValueChange(2); assert.equal(minutes, 120)
    wheels(optional)[1].props.onValueChange(17); assert.equal(minutes, 137)
    wheels(optional)[0].props.onValueChange(-1); assert.equal(minutes, null)
})
