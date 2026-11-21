const { test } = require("node:test")
const assert = require("node:assert/strict")
const loadTs = require("./load-ts.cjs")
const nodes = tree => !tree || typeof tree !== "object" ? [] : Array.isArray(tree) ? tree.flatMap(nodes) : [tree, ...nodes(tree.props?.children)]

function summary() {
    const jsx = (type, props) => ({ type, props })
    return loadTs("screens/chat/mentor-nutrition-summary.tsx", {
        "react/jsx-runtime": { jsx, jsxs: jsx },
        "react-native": { View: "View", Pressable: "Pressable", Text: "Text", StyleSheet: { create: value => value } },
        "@/screens/chat/mentor-home-data": { mentorHomeNumber: value => String(value ?? 0) },
        "@/screens/chat/mentor-nutrition-progress": { MentorCalorieRing: "Ring", MentorMacroProgress: "Bar" },
        "@/screens/chat/mentor-ui": { useMentorPalette: () => ({ blue: "#0088FF", green: "#008855", border: "#AAAAAA" }) },
    }).MentorNutritionSummary
}
const props = { consumed: { kcal: 500, protein: 20, fat: 10, carbs: 80 }, target: { kcal: 1900, protein: 130, fat: 60, carbs: 210 }, remaining: "1400", water: 250, waterGoal: 1600, animationKey: "today", dense: false, compact: false, onNutrition() {} }

test("the full-width nutrition summary shows water directly below carbs without another ring or icon buttons", () => {
    let opened = 0
    const tree = summary()({ ...props, onWater: () => opened++ }), all = nodes(tree)
    assert.equal(tree.props.style[0].width, "100%")
    assert.equal(all.filter(node => node.type === "Ring").length, 1)
    const bars = all.filter(node => node.type === "Bar")
    assert.equal(bars.length, 4); assert.equal(bars[2].props.label, "Углеводы"); assert.equal(bars[3].props.label, "Вода")
    const water = all.find(node => node.props.testID === "mentor-water-row")
    assert.ok(nodes(water).some(node => node.type === "Text" && node.props.children === "Вода"))
    assert.equal(nodes(water).some(node => node.type === "Ring"), false)
    water.props.onPress(); assert.equal(opened, 1)
})

test("water consumption and its calculated goal update directly from the saved state", () => {
    const render = summary()
    const before = nodes(render(props)).find(node => node.props.testID === "mentor-water-row")
    const after = nodes(render({ ...props, water: 750, waterGoal: 2000 })).find(node => node.props.testID === "mentor-water-row")
    assert.equal(before.props.accessibilityLabel, "Вода — 250 / 1600 мл")
    assert.equal(after.props.accessibilityLabel, "Вода — 750 / 2000 мл")
    assert.equal(nodes(after).find(node => node.type === "Bar").props.target, 2000)
})
