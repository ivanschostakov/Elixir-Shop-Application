const { test } = require("node:test")
const assert = require("node:assert/strict")
const loadTs = require("./load-ts.cjs")
const nodes = tree => !tree || typeof tree !== "object" ? [] : Array.isArray(tree) ? tree.flatMap(nodes) : [tree, ...nodes(tree.props?.children)]

function harness(reduced = false) {
    const slots = [], effects = [], scrolls = [], selected = []
    let cursor = 0
    const react = { useState(initial) { const i = cursor++; if (!(i in slots)) slots[i] = initial; return [slots[i], value => { slots[i] = value }] }, useRef(initial) { const i = cursor++; return slots[i] ??= { current: initial } }, useLayoutEffect(callback, deps) { const i = cursor++; if (!slots[i] || deps.some((value, j) => value !== slots[i][j])) { effects.push(callback); slots[i] = deps } } }
    const jsx = (type, props) => ({ type, props })
    const { MentorNutritionPager } = loadTs("screens/chat/mentor-nutrition-pager.tsx", {
        react, "react/jsx-runtime": { jsx, jsxs: jsx },
        "react-native": { View: "View", ScrollView: "ScrollView", Pressable: "Pressable", Text: "Text", useWindowDimensions: () => ({ width: 390 }), StyleSheet: { create: value => value } },
        "@/screens/chat/chat-mode-transition": { useChatReducedMotion: () => reduced },
        "@/screens/chat/mentor-home-data": { mentorHomeNumber: value => String(value ?? 0) },
        "@/screens/chat/mentor-nutrition-progress": { MentorCalorieRing: "Ring", MentorMacroProgress: "Bar" },
        "@/screens/chat/mentor-ui": { useMentorPalette: () => ({ blue: "#0088FF", green: "#008855", border: "#AAAAAA" }) },
    })
    const props = { active: "nutrition", onSelect: value => selected.push(value), consumed: { kcal: 500, protein: 20, fat: 10, carbs: 80 }, target: { kcal: 1900, protein: 130, fat: 60, carbs: 210 }, remaining: "1400", water: 250, waterGoal: 1600, animationKey: "today", dense: false, compact: false, onNutrition() {} }
    return { props, selected, scrolls, render() { cursor = 0; const tree = MentorNutritionPager(props); nodes(tree).find(node => node.type === "ScrollView").props.ref.current = { scrollTo: value => scrolls.push(value) }; effects.splice(0).forEach(callback => callback()); return tree } }
}

test("water is a separate ring, with a visible next-page edge and native horizontal snapping", () => {
    const h = harness(), tree = h.render(), scroll = nodes(tree).find(node => node.type === "ScrollView")
    assert.equal(scroll.props.horizontal, true); assert.equal(scroll.props.bounces, false)
    assert.deepEqual(scroll.props.snapToOffsets, [0, 308])
    assert.equal(scroll.props.contentContainerStyle.paddingRight, 34, "The last page can settle fully while the first leaves a visible water-ring edge")
    const rings = nodes(tree).filter(node => node.type === "Ring")
    assert.equal(rings.length, 2); assert.equal(rings[1].props.kind, "water"); assert.equal(rings[1].props.amount, 250)
    assert.equal(nodes(tree).filter(node => node.type === "Bar").length, 3, "Water is no longer a fourth macro line")
    scroll.props.onMomentumScrollEnd({ nativeEvent: { contentOffset: { x: 308 } } })
    assert.deepEqual(h.selected, ["water"])
    h.props.active = "water"; const water = h.render()
    assert.equal(nodes(water).find(node => node.props.testID === "mentor-metric-nutrition").props.accessibilityElementsHidden, true)
})

test("the water preview can be tapped and Reduce Motion also applies to page selection", () => {
    for (const reduced of [false, true]) {
        const h = harness(reduced), tree = h.render()
        nodes(tree).find(node => node.props.testID === "mentor-metric-water").props.onPress()
        assert.equal(h.selected.at(-1), "water")
        assert.deepEqual(h.scrolls.at(-1), { x: 308, animated: !reduced })
    }
})
