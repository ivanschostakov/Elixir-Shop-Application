const { test } = require("node:test")
const assert = require("node:assert/strict")
const loadTs = require("./load-ts.cjs")
const nodes = tree => !tree || typeof tree !== "object" ? [] : Array.isArray(tree) ? tree.flatMap(nodes) : [tree, ...nodes(tree.props?.children)]
const jsx = (type, props) => ({ type, props })
const flush = async () => { for (let i = 0; i < 15; i++) await Promise.resolve() }

function hooks() {
    const slots = [], effects = []; let cursor = 0
    return { reset() { cursor = 0 }, run() { effects.splice(0).forEach(fn => fn()) }, dispose() { slots.forEach(slot => slot?.cleanup?.()) }, react: {
        useState(value) { const i = cursor++; if (!(i in slots)) slots[i] = value; return [slots[i], v => { slots[i] = typeof v === "function" ? v(slots[i]) : v }] },
        useRef(value) { const i = cursor++; if (!(i in slots)) slots[i] = { current: value }; return slots[i] },
        useEffect(fn, deps) { const i = cursor++; if (!slots[i] || deps.some((v, j) => v !== slots[i].deps[j])) effects.push(() => { slots[i]?.cleanup?.(); slots[i] = { deps, cleanup: fn() } }) },
    } }
}

const recipe = { name: "Рыба с рисом", description: "Белок и овощи к ужину", portion: "1 порция", minutes: 25, nutrition: { kcal: 540, protein: 38, fat: 16, carbs: 61 }, ingredients: ["Рыба 150 г", "Рис 60 г"], steps: ["Сварите рис", "Запеките рыбу"], image: { url: "https://thumb.wikimedia.org/wikipedia/commons/fish.jpg", source_url: "https://commons.wikimedia.org/wiki/File:Fish.jpg", author: "Author", license: "CC0" } }
function harness() {
    const h = hooks(), calls = []; let reject = false, resolve
    const answer = { suggestions: [recipe], next_meal: { meal_type: "dinner", meals_left: 1, budget: { kcal: 660 }, remaining: { kcal: 660 } } }
    const module = loadTs("screens/chat/mentor-food-suggestions.tsx", {
        react: h.react, "react/jsx-runtime": { jsx, jsxs: jsx },
        "react-native": { View: "View", Text: "Text", Image: "Image", Pressable: "Button", ScrollView: "Scroll", ActivityIndicator: "Spinner", Linking: { openURL: async () => {} }, StyleSheet: { create: x => x } },
        "@/providers/language-provider": { useLanguage() {} }, "@/screens/chat/mentor-home": { MentorHomeHeader: "Header" }, "@/screens/chat/mentor-home-data": { mentorHomeNumber: String },
        "@/screens/chat/mentor-meals-data": { mealLabel: x => x }, "@/screens/chat/mentor-question-icon": { MentorQuestionIcon: "Icon" }, "@/screens/chat/mentor-ui": { useMentorPalette: () => ({}) },
        "@/services/api/companion": { requestKey: () => `key-${calls.length}` },
        "@/services/api/companion-food": { askNutritionHelp: (...args) => { calls.push(args); return reject ? Promise.reject(new Error("Offline")) : new Promise(r => { resolve = r }) } },
        "@/services/api/ai-data-consent": { AiConsentDeclinedError: class extends Error {} }, "@/utils/errors": { getErrorMessage: e => e.message },
    })
    const questions = [], controller = { askMentor: text => questions.push(text) }
    return { calls, questions, answer, finish: value => resolve(value ?? answer), fail: () => { reject = true }, recover: () => { reject = false },
        render(shown = true) { h.reset(); const tree = module.MentorFoodSuggestions({ controller, shown, onClose() {} }); h.run(); return tree }, dispose: h.dispose,
        button(tree, label) { return nodes(tree).find(node => node.props.accessibilityLabel === label) },
    }
}

test("recommendations load on opening without an input; recipes open and explicitly send one question", async () => {
    const h = harness(); h.render(false); assert.equal(h.calls.length, 0)
    h.render(); h.render(); assert.equal(h.calls.length, 1)
    assert.equal(h.calls[0][0], "suggest"); assert.equal(h.calls[0][2], null)
    h.finish(); await flush()
    let tree = h.render()
    assert.ok(h.button(tree, "Открыть рецепт: Рыба с рисом"))
    h.button(tree, "Открыть рецепт: Рыба с рисом").props.onPress()
    tree = h.render()
    assert.equal(nodes(tree).find(node => node.type === "Header").props.title, "Рецепт")
    assert.ok(nodes(tree).some(node => node.props.children === "Рыба 150 г"))
    h.button(tree, "Спросить наставника").props.onPress(); h.button(tree, "Спросить наставника").props.onPress()
    assert.equal(h.questions.length, 1); assert.match(h.questions[0], /Рыба с рисом/); assert.match(h.questions[0], /540 ккал/)
    assert.equal(h.calls.length, 1)
    h.dispose()
})

test("failed automatic requests can retry with the same id and ignore late results after dismissal", async () => {
    const h = harness(); h.fail(); h.render(); await flush()
    const tree = h.render(); assert.ok(nodes(tree).some(node => node.props.children === "Offline"))
    h.recover(); h.button(tree, "Попробовать ещё раз").props.onPress()
    assert.equal(h.calls[0][3], h.calls[1][3]); h.dispose(); h.finish(); await flush()
})

test("a queued mentor question waits for the active chat and sends once across rerenders", async () => {
    const h = hooks(), tasks = new Set(), originalSet = global.setTimeout, originalClear = global.clearTimeout
    global.setTimeout = fn => { tasks.add(fn); return fn }; global.clearTimeout = fn => tasks.delete(fn)
    try {
        const { useMentorQuestion } = loadTs("hooks/chat/use-mentor-question.ts", { react: h.react })
        const question = { id: "recipe-1", text: "Подойдёт ли рыба?" }, sent = [], acknowledged = [], errors = []
        const render = function QuestionHarness(active, busy = false) { h.reset(); useMentorQuestion({ question, active, busy, send: async text => { sent.push(text) }, handled: id => acknowledged.push(id), onError: (...args) => errors.push(args) }); h.run() }
        render(false); assert.equal(tasks.size, 0)
        render(true, true); assert.equal(tasks.size, 0)
        render(true); assert.equal(tasks.size, 1)
        render(false); assert.equal(tasks.size, 0, "Leaving the chat cancels the pending dispatch")
        render(true); for (const fn of tasks) fn(); tasks.clear(); await flush()
        render(true); render(false); render(true)
        assert.deepEqual(sent, [question.text]); assert.deepEqual(acknowledged, [question.id]); assert.equal(tasks.size, 0); assert.equal(errors.length, 0)
        h.dispose()
    } finally { global.setTimeout = originalSet; global.clearTimeout = originalClear }
})
