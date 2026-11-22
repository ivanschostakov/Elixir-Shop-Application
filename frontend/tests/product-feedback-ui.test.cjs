const assert = require("node:assert/strict")
const test = require("node:test")
const loadTs = require("./load-ts.cjs")
function fixture(panel) {
    const state = []; let cursor = 0
    const calls = []; let reject = false
    const jsx = (type, props) => ({ type, props })
    const { ProductFeedbackPanels } = loadTs("screens/product/product-feedback-panels.tsx", {
        "expo-image-picker": {},
        react: { useState: initial => { const i = cursor++; if (!(i in state)) state[i] = initial; return [state[i], value => { state[i] = typeof value === "function" ? value(state[i]) : value }] } },
        "react/jsx-runtime": { jsx, jsxs: jsx, Fragment: "Fragment" },
        "react-native": Object.fromEntries(["Image", "Pressable", "Switch", "Text", "TextInput", "View"].map(x => [x, x])),
        "react-native-svg": { Path: "Path", Svg: "Svg" },
        "@/hooks/use-theme-styles": { useThemeStyles: () => ({}) },
        "@/providers/theme-provider": { useTheme: () => ({ accentPalette: {}, palette: {} }) },
        "@/screens/product/product-screen.constants": { REVIEW_STAR_PATH: "" },
        "@/screens/product/product-screen.styles": { createProductScreenStyle: () => ({}) },
    })
    const props = {
        activePanel: panel, onChangePanel: value => { props.activePanel = value },
        onSubmitQuestion: async text => { calls.push(text); if (reject) throw Error("Offline") },
        onSubmitReview: async (...args) => { calls.push(args); if (reject) throw Error("Offline") },
        questionError: null, questionLoading: false, questionSubmitting: false, questionTotalCount: 0, questions: [],
        reviewEligibilityLoading: false, reviews: [], reviewsCanSubmit: true, reviewsError: null, reviewsLoading: false, reviewsSubmitting: false,
        reviewRatingAverage: 0, reviewTotalCount: 0, t: value => value,
    }
    function find(tree, predicate) {
        if (!tree || typeof tree !== "object") return []
        if (Array.isArray(tree)) return tree.flatMap(n => find(n, predicate))
        return [...(predicate(tree) ? [tree] : []), ...find(tree.props?.children, predicate)]
    }
    const render = () => { cursor = 0; return ProductFeedbackPanels(props) }
    const buttons = tree => find(tree, n => n.type === "Pressable")
    const action = (tree, label) => buttons(tree).find(n => find(n, x => x.type === "Text" && x.props.children === label).length)
    return { render, find, action, calls, props, fail: () => { reject = true } }
}
const flush = () => new Promise(resolve => setImmediate(resolve))

test("feedback starts with its list; write opens a form and a failed question keeps its draft", async () => {
    const h = fixture("questions")
    assert.equal(h.find(h.render(), n => n.type === "TextInput").length, 0)
    h.action(h.render(), "product.askQuestion").props.onPress()
    h.find(h.render(), n => n.type === "TextInput")[0].props.onChangeText("Question about this product")
    h.fail()
    h.action(h.render(), "product.questionSubmit").props.onPress()
    await flush()
    assert.deepEqual(h.calls, ["Question about this product"])
    assert.equal(h.find(h.render(), n => n.type === "TextInput")[0].props.value, "Question about this product")
})

test("review keeps rating and anonymity then closes its form after a successful send", async () => {
    const h = fixture("reviews")
    h.action(h.render(), "product.writeReview").props.onPress()
    h.find(h.render(), n => n.type === "TextInput")[0].props.onChangeText("Helpful product")
    h.find(h.render(), n => n.type === "Switch")[0].props.onValueChange(true)
    h.action(h.render(), "product.reviewSubmit").props.onPress()
    await flush()
    assert.deepEqual(h.calls, [[5, "Helpful product", [], true]])
    assert.equal(h.find(h.render(), n => n.type === "TextInput").length, 0)
    assert.equal(h.find(h.render(), n => n.type === "Text" && n.props.children === "product.reviewModerationNotice").length, 1)
})

test("purchase eligibility remains enforced when the review form is opened", () => {
    const h = fixture("reviews")
    h.props.reviewsCanSubmit = false
    h.action(h.render(), "product.writeReview").props.onPress()
    assert.equal(h.find(h.render(), n => n.type === "TextInput").length, 0)
    assert.equal(h.find(h.render(), n => n.type === "Text" && n.props.children === "product.reviewRequiresPurchase").length, 1)
    assert.equal(h.action(h.render(), "product.reviewSubmit"), undefined)
})
