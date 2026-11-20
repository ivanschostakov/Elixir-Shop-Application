const { test } = require("node:test")
const assert = require("node:assert/strict")
const loadTs = require("./load-ts.cjs")
const data = loadTs("screens/chat/mentor-onboarding-data.ts")
const complete = { goal: "maintain", customGoal: "", age: "32", sex: "female", height: "170", weight: "78,5", targetWeight: "75", activity: "moderate" }
const state = () => ({ available: true, consent_required: false, profile: { version: 1, enabled: true, data: {} }, mentor: { latest_weight: null } })
const nodes = tree => !tree || typeof tree !== "object" ? [] : Array.isArray(tree) ? tree.flatMap(nodes) : [tree, ...nodes(tree.props?.children)]
const label = (tree, name) => nodes(tree).find(node => (node.props.accessibilityLabel ?? node.props.title) === name)
const pane = (tree, index) => nodes(tree).find(node => node.props.testID === `mentor-optional-step-${index + 1}`)

function harness(file, overrides = {}) {
    const slots = [], effects = [], animations = []
    let cursor = 0
    const react = {
        useState(initial) { const i = cursor++; if (!(i in slots)) slots[i] = typeof initial === "function" ? initial() : initial; return [slots[i], value => { slots[i] = typeof value === "function" ? value(slots[i]) : value }] },
        useRef(initial) { const i = cursor++; if (!(i in slots)) slots[i] = { current: initial }; return slots[i] },
        useEffect(callback, deps) { const i = cursor++; if (!slots[i] || deps.some((value, j) => value !== slots[i].deps[j])) effects.push(() => { slots[i]?.cleanup?.(); slots[i] = { deps, cleanup: callback() } }) },
    }
    react.useLayoutEffect = react.useEffect
    const jsx = (type, props, key) => ({ type, props, key })
    class Value { constructor(value) { this.value = value } setValue(value) { this.value = value } interpolate(options) { return options } }
    const module = loadTs(file, {
        react, "react/jsx-runtime": { jsx, jsxs: jsx, Fragment: "Fragment" },
        "react-native": { View: "View", Text: "Text", Pressable: "Pressable", TextInput: "TextInput", Modal: "Modal", ScrollView: "ScrollView", Switch: "Switch", ActivityIndicator: "Spinner", KeyboardAvoidingView: "KeyboardAvoidingView", Keyboard: { dismiss() {} }, Platform: { OS: "ios" }, Easing: { bezier() {} }, StyleSheet: { create: value => value, absoluteFill: {}, absoluteFillObject: {} }, Animated: { Value, View: "AnimatedView", timing: (value, config) => ({ start() { animations.push(config); value.setValue(config.toValue) }, stop() {} }) } },
        "@react-native-picker/picker": { Picker: Object.assign("Picker", { Item: "PickerItem" }) },
        "react-native-safe-area-context": { useSafeAreaInsets: () => ({ top: 47, bottom: 34 }) },
        "@/providers/language-provider": { useLanguage() {} },
        "@/providers/theme-provider": { useTheme: () => ({ isDark: false, palette: { surface: "#FFFFFF" } }) },
        "@/screens/chat/mentor-ui": { MentorIcon: "Icon", useMentorPalette: () => ({ surface: "#FFFFFF" }) },
        "@/screens/chat/mentor-choice-card": { MentorChoiceCard: "ChoiceCard" },
        "@/screens/chat/mentor-custom-answer": { MentorCustomAnswer: "CustomAnswer" },
        "@/screens/chat/mentor-question-icon": { MentorQuestionIcon: "QuestionIcon" },
        "@/screens/chat/mentor-reminder-time": { MentorReminderTime: "NativeTime" },
        "@/screens/chat/chat-mode-transition": { useChatReducedMotion: () => false },
        "@/screens/chat/mentor-onboarding-data": data,
        "@/screens/chat/mentor-onboarding": { MentorOnboarding: "MentorOnboarding" },
        "@/screens/chat/mentor-onboarding-layout": { MentorFlowHeader: "FlowHeader", MentorFlowButton: "FlowButton", MentorFlowBody: "FlowBody", MentorStageTransition: "StageTransition", flowStyles: { title: {} } },
        "@/screens/chat/mentor-onboarding-optional": { MentorOptionalOnboarding: "OptionalOnboarding" },
        "@/screens/chat/mentor-nutrition-result": { MentorNutritionResult: "NutritionResult" },
        "@/screens/chat/mentor-main": { MentorMainScreen: "MentorMainScreen" },
        "@/screens/chat/companion-consent": { CompanionActionCancelled: class extends Error {} },
        "@/services/api/companion": { requestKey: () => "stable-onboarding-key" },
        "@/services/notifications/order-status-notifications": { syncPushNotifications: async () => "push-token" },
        "@/utils/errors": { getErrorMessage: error => error.message }, ...overrides,
    })
    return { animations, render(name, props) { cursor = 0; const tree = module[name](props); effects.splice(0).forEach(run => run()); return tree } }
}

test("required steps include goal weight, accept decimal commas, and omit optional fields and timezone", () => {
    for (const step of [0, 1, 2, 3, 4]) assert.equal(data.mentorStepError(complete, step), "")
    for (const [step, patch] of [[0, { goal: null }], [0, { goal: "custom" }], [1, { age: "17" }], [1, { age: "32.5" }], [1, { sex: null }], [2, { height: "49" }], [2, { weight: "0" }], [2, { weight: "Infinity" }], [3, { activity: null }]]) assert.ok(data.mentorStepError({ ...complete, ...patch }, step))
    const action = data.mentorOnboardingAction(complete, state(), "one-profile-key")
    assert.equal(action.kind, "onboard"); assert.equal(action.onboarding.current_weight_kg, 78.5)
    assert.equal(action.onboarding.target_weight_kg, 75); assert.equal(action.settings, undefined)
    assert.ok(data.mentorStepError({ ...complete, targetWeight: "" }, 4))
    assert.ok(data.mentorStepError({ ...complete, goal: "weight_loss", targetWeight: "90" }, 4))
    assert.ok(data.mentorStepError({ ...complete, goal: "weight_gain", targetWeight: "70" }, 4))
    assert.throws(() => data.mentorOnboardingAction(data.mentorFormFromState(null), state(), "bad-profile"))
})

test("complete saved data bypasses the questionnaire; partial data prefills the existing answers", () => {
    const saved = state()
    assert.equal(data.mentorProfileComplete(saved), false)
    saved.profile.data = { goal: "maintain", age: 32, sex: "female", height_cm: "170", activity: "moderate", target_weight_kg: "75" }
    assert.equal(data.mentorProfileComplete(saved), false)
    saved.mentor.latest_weight = { data: { weight_kg: "78.5" } }
    assert.equal(data.mentorProfileComplete(saved), true)
    assert.equal(data.mentorFormFromState(saved).weight, "78.5")
    saved.consent_required = true
    assert.equal(data.mentorProfileComplete(saved), false)
})

test("five retained pages animate in both directions and save after goal weight", () => {
    const h = harness("screens/chat/mentor-onboarding.tsx")
    let value = data.mentorFormFromState(null), saves = 0
    const render = () => h.render("MentorOnboarding", { visible: true, value, onChange: next => { value = next }, onClose() {}, onSave: async () => { saves++ }, saving: false, error: "" })
    const next = () => nodes(render()).find(node => node.props.testID === "mentor-onboarding-next").props.onPress()
    let tree = render()
    next(); assert.ok(nodes(render()).some(node => node.props.accessibilityRole === "alert"))
    label(render(), "Поддерживать форму").props.onPress(); next(); tree = render()
    assert.equal(h.animations.at(-1).toValue, 1); assert.equal(h.animations.at(-1).useNativeDriver, true); assert.equal(h.animations.at(-1).duration, 170)
    label(tree, "Возраст").props.onChangeText("32"); label(render(), "Женский").props.onPress(); next()
    label(render(), "Рост").props.onChangeText("170"); label(render(), "Текущий вес").props.onChangeText("78,5"); next()
    nodes(render()).find(node => node.type === "FlowHeader").props.onBack(); tree = render()
    assert.equal(label(tree, "Текущий вес").props.value, "78,5"); assert.equal(h.animations.at(-1).toValue, 2)
    assert.equal(nodes(tree).filter(node => /^mentor-onboarding-step-/.test(node.props.testID)).length, 5)
    assert.equal(saves, 0); next(); label(render(), "Умеренная активность").props.onPress(); next(); assert.equal(saves, 0)
    label(render(), "Желаемый вес").props.onChangeText("75"); next(); assert.equal(saves, 1)
})

test("Reduce Motion keeps page changes still and skips modal animation", () => {
    const h = harness("screens/chat/mentor-onboarding.tsx", { "@/screens/chat/chat-mode-transition": { useChatReducedMotion: () => true } })
    const tree = h.render("MentorOnboarding", { visible: true, value: complete, onChange() {}, onClose() {}, onSave: async () => {}, saving: false, error: "" })
    assert.equal(tree.props.animationType, "none"); assert.equal(h.animations.length, 0)
})

test("the leaf opens the question directly; final save prevents duplicate taps and offers nutrition before optional questions", async () => {
    const h = harness("screens/chat/mentor-setup.tsx")
    let calls = 0, resolve
    const c = { state: state(), initialized: true, perform: async () => { calls++; await new Promise(done => { resolve = done }) }, refresh: async () => c.state }
    const render = () => h.render("MentorSetup", { controller: c, onClose() {} })
    assert.equal(render().type, "MentorOnboarding"); assert.equal(calls, 0)
    assert.equal(label(render(), "Открыть наставника"), undefined, "No intermediate entry button")
    nodes(render()).find(node => node.type === "MentorOnboarding").props.onChange(complete)
    const save = nodes(render()).find(node => node.type === "MentorOnboarding").props.onSave()
    await nodes(render()).find(node => node.type === "MentorOnboarding").props.onSave(); assert.equal(calls, 1)
    assert.equal(nodes(render()).find(node => node.type === "MentorOnboarding").props.visible, true)
    resolve(); await save
    const nutrition = nodes(render()).find(node => node.type === "NutritionResult")
    assert.ok(nutrition); assert.ok(!nodes(render()).some(node => node.type === "OptionalOnboarding"))
    nutrition.props.onDecline()
    assert.ok(nodes(render()).some(node => node.type === "MentorMainScreen"))
})

test("failed save retains answers and retries the same operation", async () => {
    const h = harness("screens/chat/mentor-setup.tsx"), actions = []
    const c = { state: state(), initialized: true, perform: async action => { actions.push(action); if (actions.length === 1) throw Error("offline") }, refresh: async () => undefined }
    const render = () => h.render("MentorSetup", { controller: c, onClose() {} })
    nodes(render()).find(node => node.type === "MentorOnboarding").props.onChange(complete)
    await nodes(render()).find(node => node.type === "MentorOnboarding").props.onSave()
    const form = nodes(render()).find(node => node.type === "MentorOnboarding")
    assert.equal(form.props.error, "offline"); assert.equal(form.props.value.weight, "78,5")
    await form.props.onSave(); assert.deepEqual(actions[1], actions[0]); assert.ok(nodes(render()).some(node => node.type === "NutritionResult"))
})

test("an existing complete profile opens directly onto the mentor home", () => {
    const h = harness("screens/chat/mentor-setup.tsx"), saved = state()
    saved.profile.data = { goal: "maintain", age: 32, sex: "female", height_cm: "170", activity: "moderate", target_weight_kg: "75" }; saved.mentor.latest_weight = { data: { weight_kg: "78.5" } }
    const render = () => h.render("MentorSetup", { controller: { state: saved, initialized: true }, onClose() {} })
    assert.ok(nodes(render()).some(node => node.type === "MentorMainScreen"))
    assert.equal(render().type, "MentorOnboarding", "Keep one native modal when showing the mentor home")
})

test("known required answers open directly at the missing goal-weight question", () => {
    const h = harness("screens/chat/mentor-onboarding.tsx")
    const props = { visible: true, value: { ...complete, targetWeight: "" }, onChange() {}, onClose() {}, onSave: async () => {}, saving: false, error: "" }
    h.render("MentorOnboarding", props)
    const tree = h.render("MentorOnboarding", props)
    assert.equal(nodes(tree).find(node => node.type === "FlowHeader").props.step, 4)
})

test("optional answers preserve skip/resume progress and leave unrelated reminder settings untouched", () => {
    const saved = state()
    saved.profile.data = { lifestyle: "Office", preferences: "Vegetarian", onboarding_optional_step: 1 }
    saved.profile.settings = { timezone: "Asia/Almaty", course_reminders: true, nutrition_auto_eligible: false, checkin_time: "18:00", weekly_day: 6 }
    assert.equal(data.mentorOptionalResumeStep(saved), 2)
    const form = data.mentorOptionalFormFromState(saved)
    assert.equal(form.weightEnabled, false); assert.equal(form.dailyEnabled, false); assert.equal(form.weeklyEnabled, false)
    assert.deepEqual([form.weightTime, form.dailyTime, form.weeklyTime], ["08:00", "21:00", "08:00"])
    const skip = data.mentorOptionalAction(form, 2, true, saved, "skip-one")
    assert.deepEqual(skip.onboarding_details, { next_step: 3 }); assert.equal(skip.settings, undefined)
    const decline = data.mentorOptionalAction(form, 5, true, saved, "no-reminders")
    assert.equal(decline.settings.course_reminders, true); assert.equal(decline.settings.checkin_time, "18:00")
    assert.equal(decline.settings.weight_time, null); assert.equal(decline.settings.daily_time, null); assert.equal(decline.settings.weekly_time, null)
    const yes = data.mentorOptionalAction({ ...form, weightEnabled: true, weightTime: "08:15" }, 5, false, saved, "yes-reminders")
    assert.equal(yes.settings.weight_time, "08:15"); assert.equal(yes.settings.nutrition_auto_eligible, false)
    assert.equal(yes.settings.weekly_day, 0)
})

test("backtracking through completed mandatory questions always advances one screen at a time", () => {
    const h = harness("screens/chat/mentor-onboarding.tsx")
    let saves = 0
    const props = { visible: true, value: complete, onChange() {}, onClose() {}, onSave: async () => { saves++ }, saving: false, error: "" }
    const render = () => h.render("MentorOnboarding", props)
    const header = () => nodes(render()).find(node => node.type === "FlowHeader")
    render(); assert.equal(header().props.step, 4)
    for (let index = 3; index >= 0; index--) { header().props.onBack(); assert.equal(header().props.step, index) }
    for (let index = 1; index <= 4; index++) {
        nodes(render()).find(node => node.props.testID === "mentor-onboarding-next").props.onPress()
        assert.equal(header().props.step, index); assert.equal(saves, 0)
    }
    nodes(render()).find(node => node.props.testID === "mentor-onboarding-next").props.onPress()
    assert.equal(saves, 1)
    const page = nodes(render()).find(node => node.props.testID === "mentor-onboarding-step-5")
    assert.deepEqual(page.props.style[1].transform[0].translateX.outputRange, [18, 0, -18])
})

test("backtracking through saved optional questions stays sequential without redundant writes", () => {
    const h = harness("screens/chat/mentor-setup.tsx"), saved = state()
    saved.profile.data = { goal: "maintain", age: 32, sex: "female", height_cm: "170", activity: "moderate", target_weight_kg: "75", lifestyle: "Office", preferences: "Vegetarian", restrictions: "None", training_experience: "Регулярно", training_conditions: "Дома", onboarding_optional_step: 5 }
    saved.mentor.latest_weight = { data: { weight_kg: "78.5" } }
    let writes = 0
    const c = { state: saved, initialized: true, perform: async () => { writes++; return saved } }
    const render = () => h.render("MentorSetup", { controller: c, onClose() {} })
    const page = () => nodes(render()).find(node => node.type === "OptionalOnboarding")
    nodes(render()).find(node => node.type === "MentorMainScreen").props.onContinue()
    for (let index = 4; index >= 0; index--) { page().props.onBack(); assert.equal(page().props.step, index) }
    for (let index = 1; index <= 5; index++) { page().props.onNext(false); assert.equal(page().props.step, index) }
    assert.equal(writes, 0)
})

test("new optional answers transition immediately and a failed save returns to the same answer", async () => {
    const h = harness("screens/chat/mentor-setup.tsx"), saved = state()
    saved.profile.data = { goal: "maintain", age: 32, sex: "female", height_cm: "170", activity: "moderate", target_weight_kg: "75" }; saved.mentor.latest_weight = { data: { weight_kg: "78.5" } }
    let rejectSave
    const c = { state: saved, initialized: true, refresh: async () => saved, perform: () => new Promise((resolve, reject) => { rejectSave = reject }) }
    const render = () => h.render("MentorSetup", { controller: c, onClose() {} })
    const page = () => nodes(render()).find(node => node.type === "OptionalOnboarding")
    nodes(render()).find(node => node.type === "MentorMainScreen").props.onContinue()
    page().props.onChange({ ...page().props.value, lifestyle: "Evening walks" })
    page().props.onNext(false); assert.equal(page().props.step, 1); assert.equal(page().props.editingLocked, false)
    await new Promise(resolve => setImmediate(resolve)); rejectSave(Error("offline"))
    await new Promise(resolve => setImmediate(resolve))
    assert.equal(page().props.step, 0); assert.equal(page().props.value.lifestyle, "Evening walks"); assert.equal(page().props.error, "offline")
})

test("custom training answers replace all choices and the close control restores them without losing the draft", () => {
    const h = harness("screens/chat/mentor-onboarding-optional.tsx")
    let value = data.mentorOptionalFormFromState(null)
    let step = 3
    const render = () => h.render("MentorOptionalOnboarding", { value, onChange: next => { value = next }, step, onBack() {}, onClose() {}, onNext() {}, saving: false, error: "" })
    let page = pane(render(), 3)
    const choices = nodes(page).filter(node => node.type === "ChoiceCard")
    assert.equal(choices.length, 4); assert.ok(choices.every(node => node.props.description && node.props.icon))
    label(page, "Свой вариант").props.onPress()
    assert.equal(nodes(pane(render(), 3)).filter(node => node.type === "ChoiceCard").length, 0)
    nodes(pane(render(), 3)).find(node => node.type === "CustomAnswer").props.onChange("Плаваю дважды в неделю")
    assert.equal(data.mentorOptionalAction(value, 3, false, state(), "custom-experience").onboarding_details.training_experience, "Плаваю дважды в неделю")
    nodes(pane(render(), 3)).find(node => node.type === "CustomAnswer").props.onCancel()
    assert.equal(nodes(pane(render(), 3)).filter(node => node.type === "ChoiceCard").length, 4)
    label(pane(render(), 3), "Начинаю").props.onPress()
    assert.equal(nodes(pane(render(), 3)).filter(node => node.type === "CustomAnswer").length, 0)
    label(pane(render(), 3), "Свой вариант").props.onPress()
    assert.equal(nodes(pane(render(), 3)).find(node => node.type === "CustomAnswer").props.value, "Плаваю дважды в неделю")
    step = 4; page = pane(render(), 4)
    label(page, "Свой вариант").props.onPress()
    page = pane(render(), 4)
    assert.equal(nodes(page).filter(node => node.type === "ChoiceCard").length, 0)
    const custom = nodes(page).find(node => node.type === "CustomAnswer")
    custom.props.onChange("В бассейне")
    nodes(pane(render(), 4)).find(node => node.type === "CustomAnswer").props.onCancel()
    assert.equal(value.conditionsCustom, "В бассейне")
    page = pane(render(), 4)
    assert.equal(nodes(page).filter(node => node.type === "ChoiceCard").length, 4)
    label(page, "В зале").props.onPress()
    assert.equal(data.mentorOptionalAction(value, 4, false, state(), "gym-conditions").onboarding_details.training_conditions, "В зале")
    for (step of [0, 1, 2]) {
        page = pane(render(), step)
        assert.equal(nodes(page).filter(node => node.type === "ChoiceCard").length, 0)
        assert.equal(nodes(page).filter(node => node.type === "TextInput").length, 1)
    }
})

test("a custom goal also replaces the choices and keeps its draft when returning to them", () => {
    const h = harness("screens/chat/mentor-onboarding.tsx")
    let value = data.mentorFormFromState(null)
    const render = () => h.render("MentorOnboarding", { visible: true, value, onChange: next => { value = next }, onClose() {}, onSave: async () => {}, saving: false, error: "" })
    const goalPage = () => nodes(render()).find(node => node.props.testID === "mentor-onboarding-step-1")
    label(goalPage(), "Своя цель").props.onPress()
    assert.equal(nodes(goalPage()).filter(node => node.type === "ChoiceCard").length, 0)
    nodes(goalPage()).find(node => node.type === "CustomAnswer").props.onChange("Больше энергии")
    nodes(goalPage()).find(node => node.type === "CustomAnswer").props.onCancel()
    assert.equal(nodes(goalPage()).filter(node => node.type === "ChoiceCard").length, 4)
    label(goalPage(), "Своя цель").props.onPress()
    assert.equal(nodes(goalPage()).find(node => node.type === "CustomAnswer").props.value, "Больше энергии")
})

test("custom input focuses only when editable and the cross dismisses the keyboard", () => {
    let dismissed = 0, cancelled = 0
    const h = harness("screens/chat/mentor-custom-answer.tsx", { "react-native": { View: "View", Text: "Text", TextInput: "TextInput", Pressable: "Pressable", Keyboard: { dismiss() { dismissed++ } }, StyleSheet: { create: value => value } } })
    const props = { label: "Свой вариант", placeholder: "Ваш ответ", value: "Черновик", onChange() {}, onCancel() { cancelled++ }, disabled: false }
    const tree = h.render("MentorCustomAnswer", props)
    assert.equal(nodes(tree).find(node => node.type === "TextInput").props.autoFocus, true)
    const hidden = h.render("MentorCustomAnswer", { ...props, disabled: true })
    assert.equal(nodes(hidden).find(node => node.type === "TextInput").props.autoFocus, false)
    label(tree, "Вернуться к вариантам").props.onPress()
    assert.equal(dismissed, 1); assert.equal(cancelled, 1)
})

test("each reminder has an independently editable time while disabled and weekly reports use Monday", () => {
    const h = harness("screens/chat/mentor-onboarding-optional.tsx")
    const props = { label: "Отметить вес", icon: "weight", enabled: false, time: "08:00", busy: false, onToggle() {}, onTime() {} }
    const row = h.render("MentorReminderRow", props)
    assert.equal(nodes(row).find(node => node.type === "NativeTime").props.disabled, false)
    let value = data.mentorOptionalFormFromState(null)
    const render = () => h.render("MentorOptionalOnboarding", { value, onChange: next => { value = next }, step: 5, onBack() {}, onClose() {}, onNext() {}, saving: false, error: "" })
    for (const [name, time, field] of [["Отметить вес", "18:45", "weightTime"], ["Подвести итог дня", "06:30", "dailyTime"], ["Итоги недели", "13:15", "weeklyTime"]]) {
        const reminder = nodes(pane(render(), 5)).find(node => node.props.label === name)
        assert.ok(reminder.props.detail)
        reminder.props.onTime(time)
        assert.equal(value[field], time)
    }
    value = { ...value, weightEnabled: true, dailyEnabled: true, weeklyEnabled: true }
    const settings = data.mentorOptionalAction(value, 5, false, state(), "independent-times").settings
    assert.deepEqual([settings.weight_time, settings.daily_time, settings.weekly_time, settings.weekly_day], ["18:45", "06:30", "13:15", 0])
})

test("time selection uses UIDatePicker on iOS and the system time dialog on Android", () => {
    let saved, opened
    const picker = { default: "SystemTimePicker", DateTimePickerAndroid: { open: options => { opened = options } } }
    const props = { label: "Отметить вес", value: "08:00", onChange: value => { saved = value }, disabled: false }
    const ios = harness("screens/chat/mentor-reminder-time.tsx", { "@react-native-community/datetimepicker": picker })
    const view = ios.render("MentorReminderTime", props)
    const native = nodes(view).find(node => node.type === "SystemTimePicker")
    assert.equal(native.props.mode, "time"); assert.equal(native.props.display, "compact"); assert.equal(native.props.value.getHours(), 8)
    const picked = new Date(); picked.setHours(17, 35, 0, 0)
    native.props.onChange({ type: "dismissed" }, picked); assert.equal(saved, undefined)
    native.props.onChange({ type: "set" }, picked); assert.equal(saved, "17:35")
    const android = harness("screens/chat/mentor-reminder-time.tsx", { "@react-native-community/datetimepicker": picker,
        "react-native": { View: "View", Text: "Text", Pressable: "Pressable", Keyboard: { dismiss() {} }, Platform: { OS: "android" }, StyleSheet: { create: v => v } } })
    android.render("MentorReminderTime", props).props.onPress()
    assert.equal(opened.mode, "time"); assert.equal(opened.is24Hour, true)
    opened.onChange({ type: "set" }, picked); assert.equal(saved, "17:35")
})

test("the mentor home resumes optional setup and notification denial can be skipped without enabling reminders", async () => {
    let permissions = 0
    const h = harness("screens/chat/mentor-setup.tsx", { "@/services/notifications/order-status-notifications": { syncPushNotifications: async () => { permissions++; return null } } })
    const saved = state(); saved.profile.data = { goal: "maintain", age: 32, sex: "female", height_cm: "170", activity: "moderate", target_weight_kg: "75", onboarding_optional_step: 5 }; saved.mentor.latest_weight = { data: { weight_kg: "78.5" } }
    const actions = [], c = { state: saved, initialized: true, refresh: async () => saved, perform: async action => { actions.push(action); return saved } }
    const render = () => h.render("MentorSetup", { controller: c, onClose() {} })
    nodes(render()).find(node => node.type === "MentorMainScreen").props.onContinue()
    let page = nodes(render()).find(node => node.type === "OptionalOnboarding")
    assert.equal(page.props.step, 5); assert.equal(permissions, 0)
    page.props.onChange({ ...page.props.value, weightEnabled: true })
    page = nodes(render()).find(node => node.type === "OptionalOnboarding")
    page.props.onNext(false); await new Promise(resolve => setImmediate(resolve))
    assert.equal(permissions, 1); assert.equal(actions.length, 0)
    page = nodes(render()).find(node => node.type === "OptionalOnboarding")
    assert.ok(page.props.error); page.props.onNext(true); await new Promise(resolve => setImmediate(resolve))
    assert.equal(permissions, 1); assert.equal(actions[0].settings.weight_time, null)
    assert.ok(nodes(render()).some(node => node.type === "MentorMainScreen"))
})

test("nutrition result uses calculated saved values and has no questionnaire progress", () => {
    const h = harness("screens/chat/mentor-nutrition-result.tsx"), saved = state()
    saved.profile.data.nutrition = { kcal: "1900", protein: "130", fat: "60", carbs: "210" }
    const tree = h.render("MentorNutritionResult", { state: saved, onContinue() {}, onDecline() {}, onBack() {}, onClose() {} })
    const header = nodes(tree).find(node => node.type === "FlowHeader")
    assert.equal(header.props.step, undefined); assert.equal(header.props.total, undefined)
    assert.ok(nodes(tree).some(node => Array.isArray(node.props.children) && node.props.children.includes("130")))
    assert.equal(nodes(tree).filter(node => node.type === "FlowButton").length, 2)
})

test("adult onboarding calculates directly without an extra confirmation dialog", async () => {
    const { withStorageConsent } = loadTs("screens/chat/companion-consent.ts")
    const action = data.mentorOnboardingAction(complete, state(), "automatic-onboarding")
    const payload = await withStorageConsent({ ...state(), consent_required: true, consent_version: "current" }, action, () => { throw Error("No extra dialog") })
    assert.equal(payload.consent_version, "current"); assert.equal(payload.adult_confirmed, true)
    assert.equal(payload.settings, undefined)
})

test("the mentor greeting uses native glass and keeps older installed builds working", () => {
    for (const native of [true, false]) {
        const h = harness("screens/chat/mentor-shortcut.tsx", {
            "react-native-reanimated": { default: { View: "AnimatedView" }, LinearTransition: { duration: () => ({ reduceMotion: () => "system-motion" }) }, ReduceMotion: { System: "system" } },
            "@/screens/chat/native-chat-controls": { NativeChatAction: "NativeAction", NativeChatTitleMaterial: "NativeGlass", nativeChatMentorActionAvailable: true, nativeChatMentorGreetingAvailable: native },
        })
        let opened = 0, collapsed = false
        const render = () => h.render("MentorShortcut", { onPress: () => opened++, onCollapse: () => { collapsed = true }, collapsed, goal: "weight_loss" })
        let tree = render()
        const button = nodes(tree).find(node => node.props.testID === "mentor-open-shortcut")
        if (native) { assert.equal(button.props.action, "mentor"); assert.match(button.props.title, /по похудению/) }
        else assert.ok(nodes(tree).some(node => node.type === "NativeGlass"))
        nodes(tree).find(node => node.props.accessibilityLabel === "Свернуть приветствие").props.onPress()
        assert.equal(opened, 0); assert.equal(collapsed, true)
        tree = render()
        assert.equal(nodes(tree).some(node => node.props.accessibilityLabel === "Свернуть приветствие"), false)
        assert.equal(nodes(tree).find(node => node.type === "AnimatedView").props.style.width, 44)
        const round = nodes(tree).find(node => node.props.testID === "mentor-open-shortcut")
        assert.equal(round.props.title, native ? "" : undefined)
        assert.equal(round.props.label, "Открыть наставника"); round.props.onAction()
        assert.equal(opened, 1)
    }
})
