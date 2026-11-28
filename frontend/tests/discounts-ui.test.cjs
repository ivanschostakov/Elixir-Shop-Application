const assert = require("node:assert/strict")
const test = require("node:test")
const loadTs = require("./load-ts.cjs")
const { translate } = loadTs("i18n/translations.ts")
const money = loadTs("utils/settlement.ts")
const jsx = (type, props, key) => ({ type, props, key })

function all(tree, predicate) {
    if (!tree || typeof tree !== "object") return []
    if (Array.isArray(tree)) return tree.flatMap(x => all(x, predicate))
    return [...(predicate(tree) ? [tree] : []), ...all(tree.props?.children, predicate)]
}

function textOf(tree) {
    return all(tree, n => n.type === "Text").flatMap(n => n.props.children).join(" ")
}

function press(tree, label) {
    const button = all(tree, n => n.type === "Pressable" &&
        (n.props.accessibilityLabel === label || textOf(n).includes(label)))[0]
    assert.ok(button, label)
    button.props.onPress()
}

function setup(program, options = {}) {
    let user = { id: 1 }, section = null, destination = null
    const snapshot = { loyalty_program: program, fetched_at: "2026-11-21T12:00:00Z", status: "fresh",
        balance_rubles: "1250.75", total_purchases_rubles: "125000", own_promo_code: "MYCODE", referrer_promo_code: "COMPANY", ...options.account }
    const getMySettlement = async () => snapshot
    const getMyPromotions = async () => []
    const getMyAppRewards = async () => null
    const resources = new Map([
        [getMyPromotions, { data: options.promotions ?? [], error: options.offerError ?? null }],
        [getMyAppRewards, { data: { welcome_balance_rubles: "345.50", welcome_expires_at: "2026-12-01T16:00:00Z", text_review_points: 75, photo_review_points: 150 } }],
    ])
    const mocks = {
        react: { Fragment: "Fragment", useEffect: () => {}, useCallback: f => f, useRef: current => ({ current }), useState: () => [section, s => { section = s }] },
        "react/jsx-runtime": { jsx, jsxs: jsx, Fragment: "Fragment" },
        "react-native": { ...Object.fromEntries(["ActivityIndicator", "Image", "Modal", "Pressable", "ScrollView", "Text", "View"].map(x => [x, x])),
            useWindowDimensions: () => ({ width: 390, fontScale: 1 }) },
        "expo-router": { useFocusEffect: () => {}, router: { push: href => { destination = href }, dismissTo: href => { destination = href } } },
        "@/components/templates/feed-template": { FeedTemplate: "Feed" },
        "@/constants/routes": { ROUTES: { profile: "/profile", profileHistory: "/profile-history", discover: "/discover" }, getProductRoute: id => "/products/" + id },
        "@/hooks/shared/use-async-data": { useAsyncData: ({ fetcher }) => ({ data: snapshot, error: null, loading: false, reload: () => {}, ...resources.get(fetcher) }) },
        "@/hooks/use-app-safe-area-insets": { useAppSafeAreaInsets: () => ({ bottom: 20 }) },
        "@/hooks/use-theme-styles": { useThemeStyles: () => ({}) },
        "@/providers/auth-provider": { useAuth: () => ({ user, milestones: options.milestones }) },
        "@/providers/language-provider": { useLanguage: () => ({ t: translate }) },
        "@/providers/theme-provider": { useTheme: () => ({ accentPalette: {}, palette: {} }) },
        "@/screens/profile/profile-discounts-screen.styles": {},
        "@/screens/profile/discounts-menu-assets": { discountsIcons: {}, discountsHero: 1 },
        "@/services/api/settlement": { getMySettlement },
        "@/services/api/users": { getMyPromotions, detachMyReferrerCode: options.unlink },
        "@/services/api/benefits": { getMyAppRewards },
        "@/utils/settlement": money,
        "@/utils/uuid": { createUuid: () => "test-op" },
        "@/utils/errors": { getErrorMessage: e => e.message },
    }
    let slot = 0
    const state = []
    const { DiscountsDetails } = loadTs("screens/profile/discounts-details.tsx", { ...mocks, react: {
        useState(initial) {
            const i = slot++
            if (!(i in state)) state[i] = initial
            return [state[i], v => { state[i] = v }]
        },
        useRef(initial) { const i = slot++; return state[i] ??= { current: initial } },
    } })
    const { default: Screen } = loadTs("screens/profile/profile-discounts-screen.tsx", { ...mocks, "@/screens/profile/discounts-details": { DiscountsDetails } })
    const menu = () => { const root = Screen(); return root.type(root.props) }
    function details(label) {
        press(menu(), label)
        const child = all(menu(), node => node.type === DiscountsDetails)[0]
        slot = 0
        return child.type({ ...child.props, onUnlinked: () => { snapshot.referrer_promo_code = null } })
    }
    return { screen: Screen, menu, details, setUser: value => { user = value }, destination: () => destination }
}

test("unlink needs two confirmations; back or cancel submits nothing, repeated taps submit once", async () => {
    const calls = []
    const h = setup(2, { unlink: async (...args) => { calls.push(args) } })
    const codes = () => h.details("Промокоды")
    const start = () => press(codes(), "Отвязать промокод")
    const next = () => press(codes(), "Продолжить")
    start()
    assert.match(textOf(codes()), /COMPANY/)
    press(codes(), "Отмена")
    start(); next()
    assert.match(textOf(codes()), /«COMPANY» можно будет ввести снова/)
    assert.match(textOf(codes()), /с базовых 3%/)
    codes().props.onRequestClose()
    assert.deepEqual(calls, [])
    start(); next()
    const confirm = all(codes(), n => n.type === "Pressable" && textOf(n).includes("Отвязать промокод"))[0]
    await Promise.all([confirm.props.onPress(), confirm.props.onPress()])
    assert.deepEqual(calls, [["COMPANY", "test-op"]])
    assert.ok(!textOf(codes()).includes("COMPANY"))
    assert.match(textOf(codes()), /MYCODE/)
})

for (const program of [0, null, 1, 2]) {
    test(`discounts menu and program terms use the account snapshot for program ${program}`, () => {
        const h = setup(program)
        assert.ok(textOf(h.menu()).includes(money.formatSettlementMoney("1250.75", 0)))
        assert.equal(textOf(h.menu()).includes("5% бонусами"), program === 1)
        const terms = h.details("Условия программы")
        const cards = all(terms, n => n.props?.testID?.startsWith("loyalty-program-"))
        assert.equal(cards.length, 2)
        assert.deepEqual(cards.filter(n => n.props.accessibilityState.selected).map(n => n.props.testID), program === 1 || program === 2 ? [`loyalty-program-${program}`] : [])
        terms.props.onRequestClose()
        const codes = textOf(h.details("Промокоды"))
        assert.ok(codes.includes("COMPANY") && codes.includes("MYCODE"))
        h.setUser({ id: 2 })
        assert.equal(h.screen().key, 2)
        h.setUser(null)
        assert.equal(h.screen(), null)
    })
}

test("purchase navigation, rewards and welcome balance are available from the menu", () => {
    const h = setup(1)
    press(h.menu(), "Мои покупки")
    assert.equal(h.destination(), "/profile-history")
    const reviews = h.details("Бонусы за отзывы")
    assert.ok(textOf(reviews).includes("75") && textOf(reviews).includes("150"))
    press(reviews, "Найти товар в каталоге")
    assert.equal(h.destination(), "/discover")
    const welcome = h.details("Приветственный бонус")
    assert.ok(textOf(welcome).includes(money.formatSettlementMoney("345.50", 0)))
    assert.ok(textOf(welcome).includes("Действует до"))
    press(welcome, "Закрыть")
    assert.equal(all(h.menu(), n => typeof n.type === "function").length, 0)
})

test("catalog offers open their category and product routes", () => {
    const h = setup(2, { promotions: [
        { kind: "category", title: "Category A", category_id: 7, product_id: 4, discount_percent: "5" },
        { kind: "product", title: "Product B", product_id: 9, discount_percent: "12" },
    ] })
    press(h.details("Акции каталога"), "Category A")
    assert.deepEqual(h.destination(), { pathname: "/discover", params: { categoryId: "7" } })
    press(h.details("Акции каталога"), "Product B")
    assert.equal(h.destination(), "/products/9")
    const failed = setup(0, { offerError: "offline" }).details("Акции каталога")
    assert.ok(textOf(failed).includes("Повторить"))
    assert.ok(!textOf(failed).includes(translate("profile.discounts.empty")))
})

test("a deferred offer can be accepted from terms; codes do not depend on program or eligibility", () => {
    let accepted = 0, retried = 0
    const milestones = { data: { offer_partner: true, company_promo_code: "FIRM", own_promo_code: "LEGACY", own_code_eligible: false },
        accept: () => accepted++, check: () => retried++, error: null, pending: null }
    const h = setup(1, { milestones, account: { own_promo_code: null } })
    assert.match(textOf(h.menu()), new RegExp(translate("milestone.offerTitle")))
    assert.match(textOf(h.details("Условия программы")), /FIRM/)
    press(h.details("Условия программы"), translate("milestone.accept"))
    assert.equal(accepted, 1)
    milestones.pending = "accept"
    const disabled = all(h.details("Промокоды"), n => n.type === "Pressable" && textOf(n).includes(translate("milestone.accept")))
    assert.equal(disabled[0].props.disabled, true)
    milestones.pending = null
    milestones.error = "accept"
    assert.match(textOf(h.details("Промокоды")), /LEGACY/)
    press(h.details("Промокоды"), translate("common.retry"))
    assert.equal(retried, 1)
    milestones.data.offer_partner = false
    assert.ok(!textOf(h.details("Промокоды")).includes(translate("milestone.accept")))
})

test("missing settlement does not imply a zero balance or absent promo code", () => {
    const h = setup(null, { account: { fetched_at: null, status: "unavailable", balance_rubles: null, referrer_promo_code: null, own_promo_code: null } })
    assert.ok(textOf(h.menu()).includes("—"))
    const codes = textOf(h.details("Промокоды"))
    assert.ok(codes.includes(translate("profile.settlement.unavailable")))
    assert.ok(!codes.includes(translate("profile.discounts.noAttachedPromo")))
})
