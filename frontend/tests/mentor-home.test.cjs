const { test } = require("node:test")
const assert = require("node:assert/strict")
const loadTs = require("./load-ts.cjs")
const dates = loadTs("screens/chat/companion-timezones.ts")
const numbers = loadTs("screens/chat/mentor-data.ts")
const home = loadTs("screens/chat/mentor-home-data.ts", { "@/screens/chat/companion-timezones": dates, "@/screens/chat/mentor-data": numbers })
const now = new Date("2026-11-19T15:00:00Z"), clock = "UTC|0|2026-11-19"
const target = { kcal: "1900", protein: "130", fat: "60", carbs: "210" }
const entry = (id, kind, occurred_at, data = {}) => ({ id, version: 1, kind, occurred_at, data: { kind, occurred_at, ...data } })
const state = () => ({ available: true, profile: { id: 1, enabled: true, version: 1, data: { nutrition: target, onboarding_optional_step: 5 } }, entries: [], events: [], mentor: { today: { date: "2026-11-19", tasks: [], nutrition: { target, consumed: { kcal: "1240", protein: "96", fat: "48", carbs: "106" } } } } })

test("home uses server totals even when the diary preview is truncated and clamps only the visual fill", () => {
    const s = state(); s.entries = [entry(1, "meal", "2026-11-19T09:00:00Z", { nutrition: { ...target, kcal: "340" } })]
    const model = home.mentorHomeData(s, clock, now)
    assert.equal(model.consumed.kcal, "1240"); assert.equal(model.remaining, 660)
    assert.equal(home.nutritionFraction("2100", "1900"), 1)
    s.mentor.today.nutrition.consumed.kcal = "2100"
    assert.equal(home.mentorHomeData(s, clock, now).remaining, -200)
    for (const [amount, total] of [[-5, 20], [4, 0], [4, null], [Infinity, 10], ["", 20]]) assert.equal(home.nutritionFraction(amount, total), 0)
    assert.equal(home.nutritionFraction("12,5", 25), 0.5)
})

test("home selects actual local-day records, excludes future records and never reuses yesterday's totals", () => {
    const s = state()
    s.entries = [entry(1, "meal", "2026-11-18T23:30:00Z"), entry(2, "meal", "2026-11-19T05:00:00Z"), entry(3, "meal", "2026-11-19T18:00:00Z"), entry(4, "meal", "invalid")]
    const local = home.mentorHomeData(s, "UTC+05:45|0|2026-11-19", now)
    assert.deepEqual(local.meals.map(item => item.id), [1, 2])
    s.mentor.today.date = "2026-11-18"
    const stale = home.mentorHomeData(s, clock, now)
    assert.equal(stale.consumed, null); assert.equal(stale.remaining, null)
    assert.deepEqual(stale.workouts, [])
    assert.equal(home.mentorHomeNumber(undefined), "—")
    s.profile.data.nutrition = null; s.mentor.today.nutrition.target = null
    assert.equal(home.mentorHomeData(s, clock, now).consumed, null)
})

test("course preview uses the next actual pending event and hides future intakes for paused or completed plans", () => {
    const s = state(); s.plan = { status: "active" }
    s.events = [
        { id: 3, status: "pending", scheduled_at: "2026-11-21T08:00:00Z" },
        { id: 2, status: "pending", scheduled_at: "2026-11-20T08:00:00Z" },
        { id: 1, status: "done", scheduled_at: "2026-11-19T16:00:00Z" },
        { id: 4, status: "pending", scheduled_at: "2026-11-18T08:00:00Z" },
    ]
    assert.equal(home.mentorHomeData(s, clock, now).nextCourse.id, 2)
    for (const status of ["paused", "completed"]) { s.plan.status = status; assert.equal(home.mentorHomeData(s, clock, now).nextCourse, null) }
})

function harness(file, overrides = {}) {
    const slots = [], effects = [], timings = [], routes = []
    let cursor = 0
    const react = {
        useState(initial) { const i = cursor++; if (!(i in slots)) slots[i] = typeof initial === "function" ? initial() : initial; return [slots[i], value => { slots[i] = typeof value === "function" ? value(slots[i]) : value }] },
        useRef(initial) { const i = cursor++; if (!(i in slots)) slots[i] = { current: initial }; return slots[i] },
        useEffect(callback, deps) { const i = cursor++; if (!slots[i] || deps.some((value, j) => value !== slots[i].deps[j])) effects.push(() => { slots[i]?.cleanup?.(); slots[i] = { deps, cleanup: callback() } }) },
    }
    react.useLayoutEffect = react.useEffect
    react.useCallback = callback => callback
    const jsx = (type, props, key) => ({ type, props, key })
    const module = loadTs(file, {
        react, "react/jsx-runtime": { jsx, jsxs: jsx, Fragment: "Fragment" },
        "react-native": { View: "View", Text: "Text", Pressable: "Pressable", ScrollView: "ScrollView", InteractionManager: { runAfterInteractions: () => ({ cancel() {} }) }, Keyboard: { addListener: () => ({ remove() {} }), dismiss() {}, scheduleLayoutAnimation() {} }, Platform: { OS: "ios" }, useWindowDimensions: () => ({ width: 390, height: 844 }), StyleSheet: { create: v => v, absoluteFillObject: {}, hairlineWidth: 0.5 } },
        "react-native-safe-area-context": { useSafeAreaInsets: () => ({ top: 47, bottom: 34 }) },
        "@/screens/chat/mentor-navigation": { MentorBottomNavigation: "Tabs", MentorTabPages: "Pages", mentorTabs: ["nutrition", "workouts", "wellbeing", "chat"], mentorTabLabel: tab => ({ workouts: "Тренировки", wellbeing: "Самочувствие" })[tab] },
        "expo-router": { useRouter: () => ({ replace: value => routes.push(value) }) },
        "@/constants/routes": { ROUTES: { home: "/", discover: "/discover", basket: "/basket", profile: "/profile" } },
        "@/hooks/basket/basket-draft-editing-store": { useBasketDraftEditingId: () => 14 },
        "@/providers/language-provider": { useLanguage() {} },
        "@/providers/theme-provider": { useTheme: () => ({ isDark: false }) },
        "@/screens/chat/native-chat-controls": { NativeChatAction: null, nativeChatSettingsActionAvailable: false },
        "@/components/footer/sticky-footer.styles": { getNavigationFooterHeight: bottom => 52 + Math.max(16, bottom) },
        "@/screens/chat/mentor-ui": { useMentorPalette: () => ({ surface: "#FFFFFF", text: "#202923", green: "#1C694B", greenBright: "#38976A", muted: "#7D8781", border: "#DDE6DF", mint: "#E8F5EC" }) },
        "@/screens/chat/companion-timezones": dates, "@/screens/chat/mentor-home-data": home,
        "@/screens/chat/mentor-question-icon": { MentorQuestionIcon: "Icon" },
        "@/screens/chat/mentor-home": { MentorHomeScreen: "Home", MentorHomeHeader: "Header", mentorHomeStyles: {} },
        "@/screens/chat/mentor-nutrition-progress": { MentorCalorieRing: "Ring", MentorMacroProgress: "Bar" },
        "@/screens/chat/mentor-onboarding-layout": { MentorStageTransition: "Transition" },
        "@/screens/chat/companion": { CompanionPanel: "Editors" }, "@/screens/chat/mentor": { MentorWorkspace: "Workspace" },
        "@/assets/icons/dynamic-island.png": 1, "react-native-svg": { default: "Svg", Circle: "Circle" },
        "react-native-reanimated": { default: { View: "AnimatedView", createAnimatedComponent: () => "AnimatedCircle" },
            useSharedValue(value) { const i = cursor++; if (!(i in slots)) slots[i] = { value }; return slots[i] },
            useAnimatedStyle: fn => fn(), useAnimatedProps: fn => fn(), cancelAnimation() {}, Easing: { bezier() {} }, ReduceMotion: { System: "system" },
            withTiming(value, options) { timings.push(options); return value }, withDelay: (_, value) => value }, ...overrides,
    })
    return { timings, routes, render(name, props) { cursor = 0; const tree = module[name](props); effects.splice(0).forEach(run => run()); return tree } }
}
const nodes = tree => !tree || typeof tree !== "object" ? [] : Array.isArray(tree) ? tree.flatMap(nodes) : [tree, ...nodes(tree.props?.children), ...nodes(tree.props?.footer)]
const find = (tree, type) => nodes(tree).find(node => node.type === type)

test("nutrition editors, placeholder tabs, retained mentor chat and settings share one navigation", () => {
    const h = harness("screens/chat/mentor-main.tsx"), edits = []
    let continued = 0, closed = 0
    const c = { state: state(), clock, setEditor: editor => edits.push(editor), refresh: async () => c.state }
    const render = () => h.render("MentorMainScreen", { controller: c, onClose() { closed++ }, renderChat: props => ({ type: "Chat", props }), onContinue() { continued++ } })
    const page = key => find(render(), "Pages").props.render(key)
    let screen = find(page("nutrition"), "Home")
    screen.props.onAddFood(); screen.props.onMeal({ id: 42 })
    assert.deepEqual(edits, [{ page: "meal" }, { page: "meal", entry: { id: 42 } }])
    screen.props.onSettings()
    const settings = page("settings")
    nodes(settings).find(node => node.props.accessibilityLabel === "Продолжить заполнение").props.onPress(); assert.equal(continued, 1)
    nodes(settings).find(node => node.props.accessibilityLabel === "Настройки и напоминания").props.onPress(); assert.equal(edits.at(-1).page, "settings")
    find(settings, "Header").props.onBack()
    find(render(), "Tabs").props.onSelect("workouts")
    assert.equal(find(render(), "Tabs").props.active, "workouts")
    assert.ok(nodes(page("workouts")).some(node => node.props.testID === "mentor-placeholder-workouts"))
    find(render(), "Tabs").props.onSelect("wellbeing")
    assert.ok(nodes(page("wellbeing")).some(node => node.props.testID === "mentor-placeholder-wellbeing"))
    find(page("workouts"), "Header").props.onBack(); assert.equal(closed, 1)
    find(page("wellbeing"), "Header").props.onBack(); assert.equal(closed, 2)
    find(render(), "Tabs").props.onSelect("chat")
    assert.equal(find(render(), "Pages").props.footerVisible, false, "Fullscreen mentor chat hides navigation without resizing its viewport")
    assert.equal(find(page("chat"), "Chat").props.active, false, "History loading waits until the transition settles")
    find(render(), "Pages").props.onSettled("chat")
    assert.equal(find(page("chat"), "Chat").props.active, true)
    find(page("chat"), "Chat").props.onBack()
    assert.equal(find(page("chat"), "Chat").props.active, false)
    assert.equal(find(render(), "Tabs").props.active, "nutrition")
    assert.equal(find(page("nutrition"), "Home").props.onClose instanceof Function, true)
    assert.equal(page("nutrition").props.style.at(-1).paddingBottom, 86)
    assert.equal(page("chat").props.style.paddingBottom, undefined)
    const tabs = find(render(), "Tabs").props
    tabs.onSelect("workouts"); tabs.onSelect("nutrition")
    assert.equal(find(render(), "Pages").props.active, "nutrition", "The latest tap wins even before a render")
    find(page("nutrition"), "Home").props.onClose()
    assert.equal(closed, 3); assert.deepEqual(h.routes, [])
})

test("calorie and macro animations reach clamped fractions, update from the current value, and respect system Reduce Motion", () => {
    const h = harness("screens/chat/mentor-nutrition-progress.tsx")
    const props = { amount: 1240, target: 1900, label: "Calories" }
    h.render("MentorCalorieRing", props)
    const ring = find(h.render("MentorCalorieRing", props), "AnimatedCircle")
    assert.ok(Math.abs(ring.props.animatedProps.strokeDashoffset - 2 * Math.PI * 34 * (1 - 1240 / 1900)) < 0.001)
    h.render("MentorCalorieRing", { ...props, amount: 2100 })
    const full = find(h.render("MentorCalorieRing", { ...props, amount: 2100 }), "AnimatedCircle")
    assert.equal(full.props.animatedProps.strokeDashoffset, 0)
    assert.equal(h.timings.length, 2); assert.ok(h.timings.every(options => options.reduceMotion === "system" && options.duration === 900))
    const b = harness("screens/chat/mentor-nutrition-progress.tsx")
    b.render("MentorMacroProgress", { amount: 30, target: 60, label: "Fat", index: 1 })
    const bar = find(b.render("MentorMacroProgress", { amount: 30, target: 60, label: "Fat", index: 1 }), "AnimatedView")
    assert.equal(bar.props.style.at(-1).width, "50%")
})


test("one quick step moves on after today's check-in and disappears when everything is done", () => {
    const s=state(); assert.equal(home.mentorHomeData(s, clock, now).quickStep, "wellbeing")
    s.entries.push(entry(8, "wellbeing", "2026-11-19T10:00:00Z", { wellbeing: 4 }))
    assert.equal(home.mentorHomeData(s, clock, now).quickStep, "weight")
    s.mentor.latest_weight=entry(9,"weight","2026-11-19T11:00:00Z",{weight_kg: 78})
    assert.equal(home.mentorHomeData(s, clock, now).quickStep, null)
    s.mentor.today.tasks=[{kind:"workout",status:"pending",label:"Walk"}]
    assert.equal(home.mentorHomeData(s, clock, now).quickStep,"workouts")
    s.mentor.today.tasks[0].status="done"
    assert.equal(home.mentorHomeData(s, clock, now).quickStep,null)
})

test("home remains a fixed layout on small screens with no tab bar or next-step block", () => {
    const h=harness("screens/chat/mentor-home.tsx")
    const props={state:state(),clock,busy:false,onClose(){},onSettings(){},onRefresh(){},onNutrition(){},onAddFood(){},onMeal(){},onWorkout(){},onCourse(){},onWellbeing(){},onWeight(){},onAsk(){},onJournal(){}}
    h.render("MentorHomeScreen",props)
    let tree=h.render("MentorHomeScreen",props)
    nodes(tree).find(node=>node.props.testID==="mentor-home-content").props.onLayout({nativeEvent:{layout:{height:500}}})
    tree=h.render("MentorHomeScreen",props)
    assert.equal(find(tree,"ScrollView"),undefined)
    assert.equal(nodes(tree).some(node=>node.props.accessibilityRole==="tablist"),false)
    assert.equal(nodes(tree).some(node=>node.props.children==="Следующий шаг"),false)
    for (const label of ["Спросить наставника", "Самочувствие", "Тренировка", "Мой курс"]) assert.equal(nodes(tree).some(node=>node.props.accessibilityLabel===label), false)
})
