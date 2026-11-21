const { test } = require("node:test")
const assert = require("node:assert/strict")
const loadTs = require("./load-ts.cjs")
const numbers = loadTs("screens/chat/mentor-data.ts")
const meals = loadTs("screens/chat/mentor-meals-data.ts", { "@/screens/chat/companion-timezones": loadTs("screens/chat/companion-timezones.ts"), "@/screens/chat/mentor-data": numbers })
const food = loadTs("screens/chat/mentor-food-data.ts", { "@/screens/chat/mentor-data": numbers })
const estimate = () => ({ kind: "meal", name: "Рис с курицей", occurred_at: "2000-01-01T00:00:00Z", nutrition: { kcal: 450, protein: 32, fat: 12, carbs: 54 }, favorite: true })
const nodes = tree => !tree || typeof tree !== "object" ? [] : Array.isArray(tree) ? tree.flatMap(nodes) : [tree, ...nodes(tree.props?.children)]

test("food saves the full estimate for today; editing preserves identity and original time", () => {
    const now = new Date("2026-11-20T10:00:00Z")
    const action = food.foodSaveAction(estimate(), " тарелка риса ", "stable-key", undefined, now)
    assert.equal(action.record_now, true); assert.equal(action.entry.occurred_at, estimate().occurred_at); assert.equal(action.entry.note, "тарелка риса")
    assert.equal(action.entry.estimated, true); assert.equal(action.entry.favorite, false)
    const original = { id: 45, version: 3, occurred_at: "2026-11-19T12:00:00Z", data: { favorite: true } }
    const edit = food.foodSaveAction(estimate(), "new description", "edit-key", original, now)
    assert.equal(edit.resource_id, 45); assert.equal(edit.expected_version, 3)
    assert.equal(edit.entry.occurred_at, original.occurred_at); assert.equal(edit.entry.favorite, true)
    for (const nutrition of [{ kcal: 450 }, { ...estimate().nutrition, fat: -1 }, { ...estimate().nutrition, protein: Infinity }]) {
        assert.throws(() => food.foodSaveAction({ ...estimate(), nutrition }, "", "bad"))
    }
    assert.equal(food.appendFoodDictation("рис", " с курицей "), "рис с курицей")
    assert.equal(food.appendFoodDictation("x".repeat(3999), "long").length, 4000)
})

function harness(options = {}) {
    const slots = [], effects = [], calls = { alerts: [], estimates: [], saves: [], transcriptions: 0, focus: 0, record: 0 }
    let cursor = 0, sequence = 0, allowed = true
    const react = {
        useState(initial) { const i = cursor++; if (!(i in slots)) slots[i] = typeof initial === "function" ? initial() : initial; return [slots[i], value => { slots[i] = typeof value === "function" ? value(slots[i]) : value }] },
        useRef(initial) { const i = cursor++; if (!(i in slots)) slots[i] = { current: initial }; return slots[i] },
        useEffect(fn, deps) { const i = cursor++; if (!slots[i] || deps.some((value, j) => value !== slots[i].deps[j])) effects.push(() => { slots[i]?.cleanup?.(); slots[i] = { deps, cleanup: fn() } }) },
    }
    const jsx = (type, props) => ({ type, props })
    const recorder = { uri: "file:///voice.m4a", stop: async () => {}, prepareToRecordAsync: async () => {}, record() { calls.record++ }, getStatus: () => ({}) }
    const controller = { clock: "UTC|0|2026-11-20", editor: { page: "meal" }, busy: false, perform: async action => { calls.saves.push(action); if (calls.failSave) throw new Error("network") } }
    const module = loadTs("screens/chat/mentor-food.tsx", {
        react, "react/jsx-runtime": { jsx, jsxs: jsx },
        "react-native": { ActivityIndicator: "Spinner", ActionSheetIOS: { showActionSheetWithOptions: (_, fn) => fn(2) }, Alert: { alert: (title, message, buttons) => { calls.alerts.push({ title, message, buttons }); if (!calls.keepAlert) buttons.find(button => button.text === "Рассчитать так")?.onPress() } }, Image: "Image", Keyboard: { dismiss() {} }, Platform: { OS: "ios" }, Pressable: "Button", ScrollView: "ScrollView", Text: "Text", TextInput: "Input", View: "View", StyleSheet: { create: x => x } },
        "expo-image-picker": { launchImageLibraryAsync: async () => ({ canceled: false, assets: [{ uri: "file:///food.jpg" }] }) },
        "expo-audio": { RecordingPresets: { HIGH_QUALITY: {} }, setAudioModeAsync: async () => {}, useAudioRecorder: () => recorder, useAudioRecorderState: () => ({ durationMillis: 0 }) },
        "@/providers/language-provider": { useLanguage: () => ({ t: x => x }) }, "@/providers/theme-provider": { useTheme: () => ({ isDark: false }) },
        "@/screens/chat/chat-recording-permission": { requestChatRecordingPermission: async () => allowed },
        "@/screens/chat/chat-attachments": { createAttachmentFromImagePickerAsset: x => x, getVoiceRecordingFilename: () => "voice.m4a", getVoiceRecordingMimeType: () => "audio/m4a" },
        "@/screens/chat/chat-screen.constants": {}, "@/screens/chat/mentor-food-data": food,
        "@/screens/chat/mentor-home-data": { mentorHomeNumber: String }, "@/screens/chat/mentor-question-icon": { MentorQuestionIcon: "Icon" },
        "@/screens/chat/mentor-ui": { useMentorPalette: () => ({}) },
        "@/services/api/companion-food": { askNutritionHelp: async (...args) => { calls.help ??= []; calls.help.push(args); return { message: "Example nutrition answer", entry: null } }, estimateCompanionFood: async (...args) => { calls.estimates.push(args); if (calls.failEstimate) throw new Error("network"); return { entry: estimate() } } },
        "@/services/api/ai-chat": { transcribeMyAiChatVoice: async () => { calls.transcriptions++; return { text: "курица" } } },
        "@/services/api/ai-data-consent": { AiConsentDeclinedError: class extends Error {} },
        "@/screens/chat/mentor-home": { MentorHomeHeader: "HomeHeader" }, "@/screens/chat/mentor-meal-image": { MentorMealImage: "MealImage" }, "@/screens/chat/mentor-meals-data": meals,
        "@/services/api/companion": { getMealLibrary: async () => ({ entries: options.recent ?? [] }), requestKey: () => `request-${++sequence}` }, "@/utils/errors": { getErrorMessage: e => e.message },
    })
    const render = () => {
        cursor = 0
        const tree = module.MentorFoodEditor({ controller, shown: true, onClose() {}, onSaved: async () => { calls.saved = true }, helpMode: options.helpMode })
        nodes(tree).find(node => node.type === "Input")?.props.ref && (nodes(tree).find(node => node.type === "Input").props.ref.current = { focus: () => calls.focus++ })
        effects.splice(0).forEach(fn => fn())
        return tree
    }
    const button = (tree, label) => nodes(tree).find(node => node.props.accessibilityLabel === label)
    const flush = async () => { for (let i = 0; i < 20; i++) await Promise.resolve() }
    return { render, button, flush, calls, denyMicrophone: () => { allowed = false }, unmount: () => slots.forEach(slot => slot?.cleanup?.()) }
}

test("one input calculates without saving, locks double taps, and retries identical save payloads", async () => {
    const h = harness()
    let tree = h.render()
    assert.equal(nodes(tree).filter(node => node.type === "Input").length, 1)
    assert.equal(h.calls.focus, 1)
    nodes(tree).find(node => node.type === "Input").props.onChangeText("рис и курица")
    tree = h.render(); const calculate = h.button(tree, "Рассчитать КБЖУ")
    calculate.props.onPress(); calculate.props.onPress(); await h.flush()
    assert.equal(h.calls.estimates.length, 1); assert.equal(h.calls.saves.length, 0)
    tree = h.render(); h.calls.failSave = true
    h.button(tree, "Сохранить").props.onPress(); h.button(tree, "Сохранить").props.onPress(); await h.flush()
    assert.equal(h.calls.saves.length, 1)
    tree = h.render(); h.calls.failSave = false
    h.button(tree, "Сохранить").props.onPress(); await h.flush()
    assert.equal(h.calls.saves[0], h.calls.saves[1]); assert.equal(h.calls.saved, true)
})

test("calculation retries keep their key; a changed description gets a new key", async () => {
    const h = harness(); let tree = h.render()
    nodes(tree).find(node => node.type === "Input").props.onChangeText("рис"); h.calls.failEstimate = true
    tree = h.render(); h.button(tree, "Рассчитать КБЖУ").props.onPress(); await h.flush()
    tree = h.render(); h.button(tree, "Рассчитать КБЖУ").props.onPress(); await h.flush()
    assert.equal(h.calls.estimates[0][2], h.calls.estimates[1][2])
    tree = h.render(); nodes(tree).find(node => node.type === "Input").props.onChangeText("рис и курица")
    tree = h.render(); h.button(tree, "Рассчитать КБЖУ").props.onPress(); await h.flush()
    assert.notEqual(h.calls.estimates[1][2], h.calls.estimates[2][2])
})

test("dictation appends into the same input and photo-only input can be calculated", async () => {
    const h = harness(); let tree = h.render()
    nodes(tree).find(node => node.type === "Input").props.onChangeText("рис")
    tree = h.render(); h.button(tree, "Надиктовать описание").props.onPress(); await h.flush()
    tree = h.render(); h.button(tree, "Завершить диктовку").props.onPress(); await h.flush()
    tree = h.render(); assert.equal(nodes(tree).find(node => node.type === "Input").props.value, "рис курица")
    assert.equal(h.calls.transcriptions, 1); assert.equal(h.calls.estimates.length, 0); assert.equal(h.calls.saves.length, 0)
    nodes(tree).find(node => node.type === "Input").props.onChangeText("")
    tree = h.render(); h.button(tree, "Фото еды").props.onPress(); await h.flush()
    tree = h.render(); const calculate = h.button(tree, "Рассчитать КБЖУ"); assert.equal(calculate.props.disabled, false)
    calculate.props.onPress(); await h.flush(); assert.equal(h.calls.estimates[0][1].uri, "file:///food.jpg")
    h.unmount()
    const denied = harness(); denied.denyMicrophone(); denied.button(denied.render(), "Надиктовать описание").props.onPress(); await denied.flush(); assert.equal(denied.calls.record, 0)
})

test("food estimate API requires consent and sends photos through the protected multipart endpoint", async () => {
    const events = [], OriginalFormData = global.FormData
    global.FormData = class { fields = []; append(...args) { this.fields.push(args) } }
    try {
        const api = loadTs("services/api/companion-food.ts", {
            "@/services/api/client": { apiPostMultipart: async (...args) => { events.push(args); return { entry: null, message: "Уточните еду" } } },
            "@/services/api/ai-chat.constants": { aiChatEndpoint: "/ai-chat" },
            "@/services/api/ai-data-consent": { ensureAiDataConsent: async () => events.push("consent") },
        })
        await api.estimateCompanionFood(" ", { uri: "file:///food.jpg", fileName: "food.jpg", mimeType: "image/jpeg" }, "request-key")
        assert.equal(events[0], "consent"); assert.equal(events[1][0], "/ai-chat/companion/meal-estimate")
        assert.equal(events[1][2].appIntegrityAction, "ai-companion")
        assert.deepEqual(events[1][1].fields, [["text", ""], ["client_request_id", "request-key"], ["attachments", { uri: "file:///food.jpg", name: "food.jpg", type: "image/jpeg" }]])
    } finally { global.FormData = OriginalFormData }
})

test("a short description offers an optional alert and waits for the user's calculation choice", async () => {
    const h = harness(); h.calls.keepAlert = true
    let tree = h.render(); nodes(tree).find(node => node.type === "Input").props.onChangeText("омлет")
    tree = h.render(); h.button(tree, "Рассчитать КБЖУ").props.onPress(); await h.flush()
    assert.equal(h.calls.estimates.length, 0); assert.equal(h.calls.alerts[0].title, "Добавьте подробности")
    h.calls.alerts[0].buttons.find(button => button.text === "Рассчитать так").onPress(); await h.flush()
    assert.equal(h.calls.estimates.length, 1)
})

test("past meals prefill the text and private photo without estimating or saving until tapped", async () => {
    const recipe = { id: 9, data: { name: "Омлет", note: "Два яйца с помидором" }, photo_attachments: [{ id: 77 }] }
    const h = harness({ recent: [recipe] }); h.render(); await h.flush()
    let tree = h.render(); h.button(tree, "Повторить Омлет").props.onPress()
    tree = h.render(); assert.equal(nodes(tree).find(node => node.type === "Input").props.value, recipe.data.note)
    assert.equal(nodes(tree).find(node => node.type === "MealImage").props.attachment.id, 77)
    assert.equal(h.calls.estimates.length, 0); assert.equal(h.calls.saves.length, 0)
    h.button(tree, "Рассчитать КБЖУ").props.onPress(); await h.flush()
    assert.equal(h.calls.estimates[0][3], 77)
})

test("product questions use the read-only helper and never offer a save-to-diary action", async () => {
    const h = harness({ helpMode: "product" }); let tree = h.render()
    nodes(tree).find(node => node.type === "Input").props.onChangeText("Греческий йогурт")
    tree = h.render(); h.button(tree, "Узнать о продукте").props.onPress(); await h.flush()
    tree = h.render(); assert.equal(h.calls.help[0][0], "product")
    assert.equal(h.calls.saves.length, 0); assert.equal(h.calls.estimates.length, 0)
    assert.equal(h.button(tree, "Сохранить"), undefined)
    assert.ok(nodes(tree).some(node => node.props.children === "Example nutrition answer"))
})
