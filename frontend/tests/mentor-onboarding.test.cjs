const { test } = require("node:test")
const assert = require("node:assert/strict")
const loadTs = require("./load-ts.cjs")
const data = loadTs("screens/chat/mentor-onboarding-data.ts")
const complete = { goal: "maintain", customGoal: "", age: "32", sex: "female", height: "170", weight: "78,5", targetWeight: "75", activity: "moderate" }
const state = () => ({ available: true, consent_required: false, profile: { version: 1, enabled: true, data: {} }, mentor: { latest_weight: null } })
const nodes = tree => !tree || typeof tree !== "object" ? [] : Array.isArray(tree) ? tree.flatMap(nodes) : [tree, ...nodes(tree.props?.children)]
const label = (tree, name) => nodes(tree).find(node => node.props.accessibilityLabel === name)

function harness(file, overrides = {}) {
    const slots = [], effects = [], animations = []
    let cursor = 0
    const react = {
        useState(initial) { const i = cursor++; if (!(i in slots)) slots[i] = typeof initial === "function" ? initial() : initial; return [slots[i], value => { slots[i] = typeof value === "function" ? value(slots[i]) : value }] },
        useRef(initial) { const i = cursor++; if (!(i in slots)) slots[i] = { current: initial }; return slots[i] },
        useEffect(callback, deps) { const i = cursor++; if (!slots[i] || deps.some((value, j) => value !== slots[i].deps[j])) effects.push(() => { slots[i]?.cleanup?.(); slots[i] = { deps, cleanup: callback() } }) },
    }
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
        "@/screens/chat/chat-mode-transition": { useChatReducedMotion: () => false },
        "@/screens/chat/mentor-onboarding-data": data,
        "@/screens/chat/mentor-onboarding": { MentorOnboarding: "MentorOnboarding" },
        "@/screens/chat/mentor-onboarding-layout": { MentorFlowHeader: "FlowHeader", MentorFlowButton: "FlowButton", MentorFlowBody: "FlowBody", MentorStageTransition: "StageTransition", flowStyles: { title: {} } },
        "@/screens/chat/mentor-onboarding-optional": { MentorOptionalOnboarding: "OptionalOnboarding" },
        "@/screens/chat/mentor-nutrition-result": { MentorNutritionResult: "NutritionResult" },
        "@/screens/chat/mentor-development-notice": { MentorDevelopmentNotice: "MentorDevelopmentNotice" },
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
    nodes(tree).find(node => node.props.testID === "mentor-onboarding-transition").props.onLayout({ nativeEvent: { layout: { width: 390 } } })
    next(); assert.ok(nodes(render()).some(node => node.props.accessibilityRole === "alert"))
    label(render(), "Поддерживать форму").props.onPress(); next(); tree = render()
    assert.equal(h.animations.at(-1).toValue, 1); assert.equal(h.animations.at(-1).useNativeDriver, true); assert.equal(h.animations.at(-1).duration, 320)
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
    assert.ok(nodes(render()).some(node => node.type === "MentorDevelopmentNotice"))
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

test("an existing complete profile opens directly onto the placeholder", () => {
    const h = harness("screens/chat/mentor-setup.tsx"), saved = state()
    saved.profile.data = { goal: "maintain", age: 32, sex: "female", height_cm: "170", activity: "moderate", target_weight_kg: "75" }; saved.mentor.latest_weight = { data: { weight_kg: "78.5" } }
    const render = () => h.render("MentorSetup", { controller: { state: saved, initialized: true }, onClose() {} })
    assert.ok(nodes(render()).some(node => node.type === "MentorDevelopmentNotice"))
    assert.equal(render().type, "MentorOnboarding", "Keep one native modal when showing the placeholder")
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
    const skip = data.mentorOptionalAction(form, 2, true, saved, "skip-one")
    assert.deepEqual(skip.onboarding_details, { next_step: 3 }); assert.equal(skip.settings, undefined)
    const decline = data.mentorOptionalAction(form, 5, true, saved, "no-reminders")
    assert.equal(decline.settings.course_reminders, true); assert.equal(decline.settings.checkin_time, "18:00")
    assert.equal(decline.settings.weight_time, null); assert.equal(decline.settings.daily_time, null); assert.equal(decline.settings.weekly_time, null)
    const yes = data.mentorOptionalAction({ ...form, weightEnabled: true, weightTime: "08:15" }, 5, false, saved, "yes-reminders")
    assert.equal(yes.settings.weight_time, "08:15"); assert.equal(yes.settings.nutrition_auto_eligible, false)
})

test("the placeholder resumes optional setup and notification denial can be skipped without enabling reminders", async () => {
    let permissions = 0
    const h = harness("screens/chat/mentor-setup.tsx", { "@/services/notifications/order-status-notifications": { syncPushNotifications: async () => { permissions++; return null } } })
    const saved = state(); saved.profile.data = { goal: "maintain", age: 32, sex: "female", height_cm: "170", activity: "moderate", target_weight_kg: "75", onboarding_optional_step: 5 }; saved.mentor.latest_weight = { data: { weight_kg: "78.5" } }
    const actions = [], c = { state: saved, initialized: true, refresh: async () => saved, perform: async action => { actions.push(action); return saved } }
    const render = () => h.render("MentorSetup", { controller: c, onClose() {} })
    nodes(render()).find(node => node.type === "MentorDevelopmentNotice").props.onContinue()
    let page = nodes(render()).find(node => node.type === "OptionalOnboarding")
    assert.equal(page.props.step, 5); assert.equal(permissions, 0)
    page.props.onChange({ ...page.props.value, weightEnabled: true })
    page = nodes(render()).find(node => node.type === "OptionalOnboarding")
    page.props.onNext(false); await new Promise(resolve => setImmediate(resolve))
    assert.equal(permissions, 1); assert.equal(actions.length, 0)
    page = nodes(render()).find(node => node.type === "OptionalOnboarding")
    assert.ok(page.props.error); page.props.onNext(true); await new Promise(resolve => setImmediate(resolve))
    assert.equal(permissions, 1); assert.equal(actions[0].settings.weight_time, null)
    assert.ok(nodes(render()).some(node => node.type === "MentorDevelopmentNotice"))
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

test("the circular leaf uses the native glass action and supports older installed native views", () => {
    for (const native of [true, false]) {
        const h = harness("screens/chat/mentor-shortcut.tsx", { "@/screens/chat/native-chat-controls": { NativeChatAction: "NativeAction", NativeChatTitleMaterial: "NativeGlass", nativeChatMentorActionAvailable: native } })
        let opened = 0
        const tree = h.render("MentorShortcut", { onPress: () => opened++ })
        const style = native ? tree.props.style : tree.props.style({ pressed: false })[0]
        assert.equal(style.width, 44); assert.equal(style.height, 44); assert.equal(style.borderRadius, 22)
        if (native) { assert.equal(tree.props.action, "mentor"); tree.props.onAction() }
        else { assert.ok(nodes(tree).some(node => node.type === "NativeGlass")); tree.props.onPress() }
        assert.equal(opened, 1)
    }
})
