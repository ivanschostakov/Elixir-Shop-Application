const { test } = require("node:test")
const assert = require("node:assert/strict")
const loadTs = require("./load-ts.cjs")
const dates = loadTs("screens/chat/companion-timezones.ts"), numeric = loadTs("screens/chat/mentor-data.ts")
const meals = loadTs("screens/chat/mentor-meals-data.ts", { "@/screens/chat/companion-timezones": dates, "@/screens/chat/mentor-data": numeric })
const home = loadTs("screens/chat/mentor-home-data.ts", { "@/screens/chat/companion-timezones": dates, "@/screens/chat/mentor-data": numeric })
const clock = "UTC|0|2030-01-10"

test("meals group several dishes, preserve additional meal groups and infer legacy records in device timezone", () => {
    const entry = (id, data, at = "2030-01-10T13:00:00Z") => ({ id, occurred_at: at, kind: "meal", data: { nutrition: { kcal: "100", protein: "10", fat: "2", carbs: "11" }, ...data } })
    const groups = meals.mealGroups([entry(1, { meal_type: "breakfast" }), entry(2, { meal_type: "breakfast" }), entry(3, {}), entry(4, { meal_type: "extra", meal_key: "a" }), entry(5, { meal_type: "extra", meal_key: "b" })], clock)
    assert.equal(groups.length, 5); assert.equal(groups[0].total.kcal, 200); assert.equal(groups[1].total.kcal, 100)
    assert.deepEqual(groups.slice(3).map(group => group.key), ["a", "b"])
    assert.equal(meals.suggestedMeal("UTC+05:45|0|2030-01-10", "2030-01-10T13:00:00Z"), "dinner")
    assert.equal(meals.needsFoodDetails("омлет", false), true)
    assert.equal(meals.needsFoodDetails("омлет", true), false)
    assert.equal(meals.needsFoodDetails("два яйца с сыром", false), false)
    for (const water of ["300 мл воды", "выпил 0.5 л воды", "water 250 ml", "300 мл су"]) assert.equal(meals.needsFoodDetails(water, false), false)
})

test("a fast or slow phone clock does not hide freshly saved food or move the dashboard to another day", () => {
    const server = "2030-01-10T23:59:50Z", received = Date.parse("2030-01-11T00:02:50Z")
    const state = { as_of: server, received_at: received, entries: [{ id: 1, kind: "meal", occurred_at: server, data: {} }], mentor: { today: { date: "2030-01-10", nutrition: { consumed: { kcal: 1270 }, target: { kcal: 3069 } } } } }
    const value = home.mentorHomeData(state, clock, new Date(received + 2000))
    assert.equal(value.date, "2030-01-10"); assert.equal(value.meals.length, 1); assert.equal(value.remaining, 1799)
    state.received_at = Date.parse("2030-01-10T23:57:00Z")
    assert.equal(home.mentorHomeData(state, clock, new Date(state.received_at + 2000)).meals.length, 1)
})

test("a late refresh cannot overwrite the complete state returned after a successful food save", async () => {
    const slots = []; let cursor = 0, releaseRefresh
    const before = { available: true, profile: { enabled: true }, dialogue_protocol: 2, entries: [] }
    const after = { ...before, entries: [{ id: 1 }], mentor: { today: { nutrition: { consumed: { kcal: 1270 } } } } }
    const react = { useState(initial) { const i = cursor++; if (!(i in slots)) slots[i] = typeof initial === "function" ? initial() : initial; return [slots[i], value => { slots[i] = typeof value === "function" ? value(slots[i]) : value }] }, useRef(initial) { const i = cursor++; return slots[i] ??= { current: initial } }, useCallback: fn => fn, useEffect() {} }
    const { useCompanion } = loadTs("screens/chat/companion.tsx", {
        react, "@react-navigation/native": { useIsFocused: () => true },
        "@/screens/chat/mentor-wellbeing-form": { MentorWellbeingEditor: "WellbeingEditor" },
        "@/components/platform/app-form-layout": { AppFormLayout: "KeyboardAvoidingView" },
        "react-native": { Platform: { OS: "ios" }, StyleSheet: { create: value => value } },
        "@/providers/language-provider": { useLanguage() {} }, "@/hooks/chat/use-device-clock": { useDeviceClock: () => clock },
        "@/hooks/basket/use-basket-mutations": {}, "@/utils/errors": { getErrorMessage: e => e.message },
        "@/services/api/companion": { getCompanionAvailability: async () => before, getCompanion: () => new Promise(resolve => { releaseRefresh = resolve }), actCompanion: async () => ({ state: after }), requestKey: () => "test-save-key" },
        "@/screens/chat/companion-consent": { withStorageConsent: async (_state, action) => action },
        "@/screens/chat/companion-timezones": dates, "@/screens/chat/companion-dialogue": {}, "@/screens/chat/mentor-data": {},
        "@/screens/chat/mentor-question-icon": {}, "@/screens/chat/mentor-ui": {}, "@/screens/chat/mentor-meal-screens": {},
    })
    const render = function CompanionHarness() { cursor = 0; return useCompanion(true) }
    const pending = render().refresh(); await Promise.resolve(); await Promise.resolve()
    await render().perform({ kind: "entry" })
    assert.equal(render().state.mentor.today.nutrition.consumed.kcal, 1270)
    releaseRefresh(before); await pending
    assert.equal(render().state.mentor.today.nutrition.consumed.kcal, 1270)
    assert.equal(render().state.entries.length, 1); assert.equal(render().initialized, true)
})
