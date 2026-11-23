const test = require("node:test")
const assert = require("node:assert/strict")
const load = require("./load-ts.cjs")
const dates = load("screens/chat/companion-timezones.ts")
const data = load("screens/chat/mentor-wellbeing-data.ts", { "@/screens/chat/companion-timezones": dates })
const jsx = (type, props) => ({ type, props })
const runtime = { jsx, jsxs: jsx, Fragment: "Fragment" }
const nodes = tree => !tree || typeof tree !== "object" ? [] : Array.isArray(tree) ? tree.flatMap(nodes) : [tree, ...nodes(tree.props?.children)]
const complete = () => ({ wellbeing: 4, energy: 4, mood: 2, stress: 2, sleepMinutes: 450, sleepQuality: 3, appetite: 3, note: "" })
const row = (id, at, fields = {}) => ({ id, version: 3, kind: "wellbeing", occurred_at: at, data: { kind: "wellbeing", occurred_at: at, wellbeing: 4, ...fields } })

test("wellbeing drafts have no guessed answers and preserve legacy appetite and sleep precision", () => {
    const draft = data.wellbeingDraft()
    assert.ok(Object.entries(draft).every(([field, value]) => field === "note" ? value === "" : value === null))
    assert.equal(data.wellbeingStepComplete(0, draft), false)
    assert.equal(data.wellbeingStepComplete(3, { ...complete(), sleepMinutes: 0 }), true)
    assert.equal(data.wellbeingStepComplete(3, { ...complete(), sleepMinutes: 1441 }), false)
    const original = row(7, "2026-11-19T15:10:32.123Z", { appetite: 2, sleep_hours: "7.12345", note: "Exact older note", estimated: true })
    const edited = { ...data.wellbeingDraft(original.data), mood: 2, stress: 1, sleepQuality: 3, energy: 4 }
    const action = data.wellbeingSaveAction(edited, "2026-11-19", "same-key", original, new Date("2026-11-22T15:00:00Z"))
    assert.equal(action.resource_id, 7); assert.equal(action.expected_version, 3)
    assert.equal(action.entry.occurred_at, original.occurred_at)
    assert.equal(action.entry.sleep_hours, "7.12345")
    assert.equal(action.entry.appetite, 2); assert.equal(action.entry.note, "Exact older note"); assert.equal(action.entry.estimated, true)
    assert.equal(data.appetiteChoice(2), 0); assert.equal(data.appetiteChoice(4), 2)
})

test("new check-ins use the chosen local date and reject future, invalid or incomplete entries", () => {
    const now = new Date(2026, 10, 22, 7, 15)
    const today = data.wellbeingSaveAction(complete(), "2026-11-22", "today-key", undefined, now)
    assert.equal(today.entry.occurred_at, now.toISOString())
    const past = data.wellbeingSaveAction(complete(), "2026-11-01", "past-key", undefined, now)
    assert.equal(dates.localDateTime(past.entry.occurred_at).slice(0, 10), "2026-11-01")
    assert.equal(past.entry.sleep_hours, 7.5)
    for (const day of ["2026-11-23", "2026-02-30", "invalid"]) assert.throws(() => data.wellbeingSaveAction(complete(), day, "bad", undefined, now))
    assert.throws(() => data.wellbeingSaveAction({ ...complete(), mood: null }, "2026-11-22", "missing", undefined, now))
    assert.throws(() => data.wellbeingSaveAction({ ...complete(), note: "x".repeat(501) }, "2026-11-22", "long", undefined, now))
})

test("calendar dots follow local days, select the latest record and retain earlier days in dense months", async () => {
    const result = data.wellbeingDays([row(1, "2026-11-21T20:00:00Z"), row(2, "2026-11-21T22:00:00Z"), row(3, "2026-11-21T22:00:00Z"), row(4, "2026-11-23T00:00:00Z")], "UTC+05:45|0|2026-11-22", "2026-11-22")
    assert.deepEqual(Object.keys(result), ["2026-11-22"]); assert.equal(result["2026-11-22"].id, 3)
    assert.deepEqual(data.wellbeingMonthBounds("2024-02"), { from: "2024-02-01", to: "2024-03-01" })
    assert.deepEqual(data.wellbeingMonthBounds("2026-12"), { from: "2026-12-01", to: "2027-01-01" })
    const calls = []
    const loaded = await data.loadWellbeingMonth("2026-11", async (from, to) => {
        calls.push([from, to])
        return { entries: from === "2026-11-01" && to === "2026-12-01" ? Array.from({ length: 200 }, () => row(1, "2026-11-29T12:00:00Z")) : [row(from.endsWith("01") ? 7 : 8, `${from}T12:00:00Z`)] }
    })
    assert.deepEqual(loaded.map(entry => entry.id), [7, 8])
    assert.deepEqual(calls, [["2026-11-01", "2026-12-01"], ["2026-11-01", "2026-11-16"], ["2026-11-16", "2026-12-01"]])
})

function editorHarness() {
    const slots = [], effects = [], calls = { saved: [], closed: 0 }
    let cursor = 0, sequence = 0, fail = true
    const react = {
        useState(initial) { const i = cursor++; if (!(i in slots)) slots[i] = typeof initial === "function" ? initial() : initial; return [slots[i], next => { slots[i] = typeof next === "function" ? next(slots[i]) : next }] },
        useRef(initial) { const i = cursor++; return slots[i] ??= { current: initial } },
        useEffect(fn) { effects.push(fn) },
    }
    const { MentorWellbeingEditor } = load("screens/chat/mentor-wellbeing-form.tsx", {
        react, "react/jsx-runtime": { jsx: (type, props) => type === "Transition" ? jsx(type, { ...props, children: props.render(props.step) }) : jsx(type, props), jsxs: (type, props) => type === "Transition" ? jsx(type, { ...props, children: props.render(props.step) }) : jsx(type, props), Fragment: "Fragment" },
        "react-native": { ActivityIndicator: "Spinner", Pressable: "Button", ScrollView: "Scroll", Text: "Text", TextInput: "Input", View: "View" },
        "@react-native-picker/picker": { Picker: Object.assign(function Picker() {}, { Item: "Item" }) },
        "react-native-safe-area-context": { useSafeAreaInsets: () => ({ top: 62, bottom: 34 }) },
        "@/providers/language-provider": { useLanguage: () => ({ language: "ru" }) },
        "@/providers/theme-provider": { useTheme: () => ({ isDark: false }) },
        "@/components/platform/app-surface": { AppSurface: "Surface" },
        "@/components/platform/app-level-slider": { AppLevelSlider: "Slider" },
        "@/components/platform/app-step-transition": { AppStepTransition: "Transition" },
        "react-native-reanimated": { default: { View: "AnimatedView" } },
        "@/screens/chat/mentor-home": { MentorHomeHeader: "Header" },
        "@/screens/chat/mentor-ui": { useMentorPalette: () => ({}) },
        "@/screens/chat/companion-consent": { CompanionActionCancelled: class extends Error {} },
        "@/screens/chat/companion-timezones": dates,
        "@/services/api/companion": { requestKey: () => `key-${++sequence}` },
        "@/utils/errors": { getErrorMessage: error => error.message },
        "@/screens/chat/mentor-wellbeing-data": data,
        "@/screens/chat/mentor-wellbeing-icons": { WellbeingIcon: "Icon" },
        "@/screens/chat/mentor-wellbeing.styles": { wellbeingStyles: {} },
    })
    const entry = row(12, "2026-11-21T12:00:00Z", { ...data.wellbeingSaveAction(complete(), "2026-11-21", "seed", undefined, new Date(2026, 10, 22)).entry })
    const controller = { editor: { page: "wellbeing", date: "2026-11-21", entry }, clock: "UTC|0|2026-11-22", busy: false,
        async perform(action) { calls.saved.push(action); if (fail) throw Error("Connection lost") },
    }
    const render = () => { cursor = 0; return MentorWellbeingEditor({ controller, onClose: () => calls.closed++ }) }
    const next = () => nodes(render()).find(node => node.props.accessibilityLabel === "Next" || node.props.accessibilityLabel === "Далее").props.onPress()
    const findSave = () => nodes(render()).find(node => node.props.accessibilityLabel === "Save entry" || node.props.accessibilityLabel === "Сохранить запись")
    const flush = async () => { for (let i = 0; i < 15; i++) await Promise.resolve() }
    return { render, next, findSave, flush, calls, controller, succeed() { fail = false } }
}

test("six-step editing preserves answers on Back and retries the same complete action after a failed save", async () => {
    const h = editorHarness()
    h.next(); h.next()
    nodes(h.render()).find(node => node.type === "Header").props.onBack()
    h.next(); h.next(); h.next(); h.next()
    const input = nodes(h.render()).find(node => node.type === "Input")
    input.props.onChangeText("After a walk")
    h.findSave().props.onPress(); h.findSave().props.onPress()
    await h.flush()
    assert.equal(h.calls.saved.length, 1, "repeated taps cannot create duplicate actions")
    assert.equal(h.calls.closed, 0)
    assert.equal(nodes(h.render()).find(node => node.type === "Input").props.value, "After a walk")
    assert.ok(nodes(h.render()).some(node => node.props.children === "Connection lost"))
    h.succeed(); h.findSave().props.onPress(); await h.flush()
    assert.equal(h.calls.saved.length, 2)
    assert.strictEqual(h.calls.saved[0], h.calls.saved[1])
    assert.equal(h.calls.saved[1].resource_id, 12); assert.equal(h.calls.saved[1].expected_version, 3)
    assert.equal(h.calls.saved[1].entry.note, "After a walk")
    assert.equal(h.calls.closed, 1)
})

test("calendar opens a loaded day's existing entry and ignores stale months or failed reads", async () => {
    const slots = [], effects = [], requests = [], edits = []
    let cursor = 0
    const react = {
        useState(initial) { const i = cursor++; if (!(i in slots)) slots[i] = typeof initial === "function" ? initial() : initial; return [slots[i], next => { slots[i] = typeof next === "function" ? next(slots[i]) : next }] },
        useRef(initial) { const i = cursor++; return slots[i] ??= { current: initial } },
        useCallback: fn => fn,
        useEffect(fn, deps) { const i = cursor++; if (!slots[i] || deps.some((value, j) => value !== slots[i].deps[j])) effects.push(() => { slots[i]?.cleanup?.(); slots[i] = { deps, cleanup: fn() } }) },
    }
    const { MentorWellbeingScreen } = load("screens/chat/mentor-wellbeing.tsx", {
        react, "react/jsx-runtime": runtime,
        "react-native": { ActivityIndicator: "Spinner", Pressable: "Button", ScrollView: "Scroll", Text: "Text", View: "View", useWindowDimensions: () => ({ width: 440, height: 956 }) },
        "react-native-calendars": { LocaleConfig: { locales: {} } },
        "@/components/platform/app-calendar": { AppCalendar: "Calendar" },
        "@/providers/language-provider": { useLanguage: () => ({ language: "ru" }) },
        "@/providers/theme-provider": { useTheme: () => ({ isDark: false }) },
        "@/screens/chat/mentor-home": { MentorHomeHeader: "Header" },
        "@/screens/chat/companion-timezones": dates,
        "@/screens/chat/mentor-ui": { useMentorPalette: () => ({}) },
        "@/services/api/companion": {},
        "@/utils/errors": { getErrorMessage: error => error.message },
        "@/screens/chat/mentor-wellbeing-data": { ...data, loadWellbeingMonth: month => new Promise((resolve, reject) => requests.push({ month, resolve, reject })) },
        "@/screens/chat/mentor-wellbeing-icons": { WellbeingIcon: "Icon" },
        "@/screens/chat/mentor-wellbeing.styles": { wellbeingStyles: {} },
    })
    const today = dates.calendarDate()
    const controller = { clock: dates.deviceClockKey(), state: {}, busy: false, setEditor: value => edits.push(value) }
    const render = () => { cursor = 0; const tree = MentorWellbeingScreen({ controller, active: true }); effects.splice(0).forEach(fn => fn()); return nodes(tree) }
    const calendar = () => { const tree = render(); assert.ok(!tree.some(node => node.type === "Scroll"), "the main calendar must not scroll"); return tree.find(node => node.type === "Calendar") }
    const layout = () => render().filter(node => node.type === "Calendar" || ["wellbeing-day-card", "wellbeing-action-footer"].includes(node.props.testID)).map(node => node.props.style)
    const metrics = () => render().filter(node => node.props.testID?.startsWith("wellbeing-metric-"))
    const flush = async () => { for (let i = 0; i < 20; i++) await Promise.resolve() }
    const loadingLayout = layout()
    assert.equal(metrics().length, 4, "all four overview cells exist before any data arrives")
    assert.equal(metrics().flatMap(nodes).filter(node => node.props.children === "—").length, 4)
    calendar().props.onDayPress({ dateString: today })
    assert.equal(edits.length, 0)
    const existing = row(42, new Date().toISOString())
    requests[0].resolve([existing]); await flush()
    assert.deepEqual(layout(), loadingLayout, "loading and saved entries keep the calendar, summary and footer geometry")
    assert.equal(metrics().length, 4)
    assert.ok(metrics().flatMap(nodes).some(node => node.props.children === "Good" || node.props.children === "Хорошо"))
    assert.equal(metrics().flatMap(nodes).filter(node => node.props.children === "—").length, 3, "older partial records retain placeholders for missing answers")
    calendar().props.onDayPress({ dateString: dates.shiftCalendarDay(today, 1) })
    assert.equal(edits.length, 0)
    calendar().props.onDayPress({ dateString: today })
    assert.equal(edits[0].entry, existing); assert.equal(edits[0].date, today)
    calendar().props.onMonthChange({ dateString: "2026-09-01" }); render()
    calendar().props.onMonthChange({ dateString: "2026-08-01" }); render()
    requests[1].resolve([row(11, "2026-09-02T12:00:00Z")]); await flush()
    assert.equal(calendar().props.disabledByDefault, true)
    requests[2].resolve([row(12, "2026-08-02T12:00:00Z")]); await flush()
    assert.deepEqual(layout(), loadingLayout, "months with a different week count keep the same layout")
    calendar().props.onDayPress({ dateString: "2026-08-02" })
    assert.equal(edits.at(-1).entry.id, 12)
    controller.state = {}; render()
    assert.equal(requests.length, 3, "background companion polling must not reload the calendar")
    controller.wellbeingRevision = 1; render()
    requests[3].reject(Error("Offline")); await flush()
    const count = edits.length
    calendar().props.onDayPress({ dateString: "2026-08-02" })
    assert.equal(edits.length, count, "failed refresh must not open a new entry over an unknown existing record")
    assert.ok(render().some(node => node.props.children === "Offline"))
    assert.deepEqual(layout(), loadingLayout, "errors do not move the action button or remove metric cells")
})

test("every wellbeing choice and questionnaire heading is translated for both supported secondary languages", () => {
    const { mentorTranslations } = load("i18n/mentor-translations.ts")
    for (const list of [data.wellbeingLabels, data.energyLabels, data.moodLabels, data.stressLabels, data.sleepQualityLabels, data.appetiteLabels]) {
        for (const label of list) for (const language of ["en", "kz"]) assert.ok(mentorTranslations[label]?.[language])
    }
})

test("neutral and happy faces, appetite and energy levels use distinct source SVGs", () => {
    const fs = require("node:fs"), path = require("node:path")
    const mocks = { "react/jsx-runtime": runtime, "react-native-svg": { default: "Svg", Line: "Line", Path: "Path" }, "@/assets/icons/mentor/leaf.svg": { default: "leaf" } }
    const folder = path.join(path.dirname(require.resolve("../package.json")), "assets/icons/mentor/wellbeing")
    for (const file of fs.readdirSync(folder).filter(file => file.endsWith(".svg"))) mocks[`@/assets/icons/mentor/wellbeing/${file}`] = { default: file }
    const { WellbeingIcon } = load("screens/chat/mentor-wellbeing-icons.tsx", mocks)
    for (const [name, count] of [["face", 5], ["energy", 5], ["apple", 3], ["moon", 3], ["stress", 5]]) {
        const icons = Array.from({ length: count }, (_, index) => WellbeingIcon({ name, level: index + 1, color: "green" }).type)
        assert.equal(new Set(icons).size, count, name)
        const geometry = icons.filter(icon => icon.endsWith(".svg")).map(icon => fs.readFileSync(path.join(folder, icon), "utf8").replace(/class="[^"]+"/g, ""))
        assert.equal(new Set(geometry).size, geometry.length)
    }
    assert.equal(WellbeingIcon({ name: "face", level: 3, color: "green" }).type, "meh.svg")
    assert.equal(WellbeingIcon({ name: "face", level: 5, color: "green" }).type, "laugh.svg")
})
