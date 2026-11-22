const assert = require("node:assert/strict")
const test = require("node:test")
const loadTs = require("./load-ts.cjs")
const { translate } = loadTs("i18n/translations.ts")
const money = loadTs("utils/settlement.ts")
const jsx = (type, props, key) => ({ type, props, key })

function setup(program) {
    let user = { id: 1 }
    const snapshot = { loyalty_program: program, fetched_at: "2026-11-21T12:00:00Z", status: "fresh", balance_rubles: "1000.00", total_purchases_rubles: "125000", own_promo_code: "MYCODE", referrer_promo_code: "COMPANY" }
    const { default: Screen } = loadTs("screens/profile/profile-discounts-screen.tsx", {
        react: { useCallback: f => f, useRef: current => ({ current }) },
        "react/jsx-runtime": { jsx, jsxs: jsx },
        "react-native": Object.fromEntries(["ActivityIndicator", "Image", "Pressable", "Text", "View"].map(x => [x, x])),
        "expo-linear-gradient": { LinearGradient: "Gradient" },
        "expo-router": { useFocusEffect: () => {}, router: { push: () => {} } },
        "@/components/templates/feed-template": { FeedTemplate: "Feed" },
        "@/constants/routes": { ROUTES: {}, getProductRoute: () => "/product" },
        "@/hooks/shared/use-async-data": { useAsyncData: ({ initialData }) => ({ data: Array.isArray(initialData) ? [] : snapshot, loading: false, error: null, reload: () => {} }) },
        "@/hooks/use-theme-styles": { useThemeStyles: () => ({}) },
        "@/providers/auth-provider": { useAuth: () => ({ user }) },
        "@/providers/language-provider": { useLanguage: () => ({ t: translate }) },
        "@/providers/theme-provider": { useTheme: () => ({ accentPalette: {}, palette: {} }) },
        "@/screens/profile/profile-discounts-screen.styles": { createProfileDiscountsScreenStyles: () => ({}) },
        "@/services/api/settlement": { getMySettlement: async () => snapshot },
        "@/services/api/users": { getMyPromotions: async () => [] },
        "@/utils/settlement": money,
    })
    return { screen: () => Screen(), setUser: value => { user = value } }
}
function all(tree, predicate) {
    if (!tree || typeof tree !== "object") return []
    if (Array.isArray(tree)) return tree.flatMap(x => all(x, predicate))
    return [...(predicate(tree) ? [tree] : []), ...all(tree.props?.children, predicate)]
}
for (const program of [0, null, 1, 2]) {
    test(`discounts show both program guides and select only authoritative program ${program}`, () => {
        const h = setup(program)
        const root = h.screen()
        const tree = root.type(root.props)
        const cards = all(tree, n => n.props?.testID?.startsWith("loyalty-program-"))
        assert.equal(cards.length, 2)
        assert.deepEqual(cards.filter(n => n.props.accessibilityState.selected).map(n => n.props.testID), program === 1 || program === 2 ? [`loyalty-program-${program}`] : [])
        const text = all(tree, n => n.type === "Text").map(n => n.props.children).flat().join(" ")
        assert.ok(text.includes("Программы и преимущества"))
        assert.ok(text.includes("COMPANY") && text.includes("MYCODE"))
        assert.ok(text.includes(money.formatSettlementMoney("1000.00")), "Available balance is visible in the program screen")
        h.setUser({ id: 2 })
        assert.equal(h.screen().key, 2)
        h.setUser(null)
        assert.equal(h.screen(), null)
    })
}
