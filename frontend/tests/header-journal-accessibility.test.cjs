const { test } = require("node:test")
const assert = require("node:assert/strict")
const load = require("./load-ts.cjs")
const elements = tree => Array.isArray(tree) ? tree.flatMap(elements) : tree?.props ? [tree, ...elements(tree.props.children)] : []
const rn = { Modal: "Modal", Text: "Text", Pressable: "Pressable", View: "View", ScrollView: "Scroll", TextInput: "Input", StyleSheet: { absoluteFill: {}, create: value => value } }
const theme = { useTheme: () => ({ palette: {} }) }

test("menu and search leave the short header's native bounds, dismiss and navigate", () => {
    let closed = 0, pushed, open = false
    const onClose = () => { closed++ }
    const styles = load("components/header/app-header.styles.ts", { "react-native": rn }).getHeaderStyles(48, {})
    const { HeaderOverlay } = load("components/header/header-overlay.tsx", {
        "react-native": rn, "react-native-safe-area-context": { SafeAreaProvider: "Provider", SafeAreaView: "Safe" },
        "@/providers/theme-provider": theme,
    })
    const modal = HeaderOverlay({ onClose, closeLabel: "Close", children: "panel" })
    assert.equal(modal.type, "Modal")
    modal.props.onRequestClose()
    elements(modal).find(el => el.props.accessibilityLabel === "Close").props.onPress()
    assert.equal(closed, 2)
    const mocks = { "react-native": rn, "react-native-svg": {}, "@/providers/theme-provider": theme, "@/components/header/header-overlay": { HeaderOverlay } }
    const { HeaderMenu } = load("components/header/header-menu.tsx", mocks)
    const menu = () => elements(HeaderMenu({ t: k => k, styles, isOpen: open, onToggle: () => { open = !open }, onClose }))
    assert.ok(!menu().some(el => el.type === HeaderOverlay))
    menu().find(el => el.props.accessibilityLabel === "nav.menu").props.onPress()
    assert.ok(menu().find(el => el.type === HeaderOverlay))
    assert.equal(styles.menuPopup.position, undefined)
    const { HeaderSearchPanel } = load("components/header/header-search-panel.tsx", {
        ...mocks, react: { useEffect() {} }, "expo-router": { useRouter: () => ({ push: value => { pushed = value } }) },
        "@/components/header/app-header.constants": {}, "@/components/content/product-content": { getProductContentSubtitle: () => "" },
        "@/constants/routes": { ROUTES: {}, getProductRoute: id => "/product/" + id },
        "@/hooks/products/use-product-search": { useProductSearch: () => ({ clearSearch() {}, setQuery() {}, products: [{ id: 9, name: "Result" }], query: "Res" }) },
    })
    const panel = HeaderSearchPanel({ t: k => k, visible: true, onClose, styles })
    assert.equal(panel.type, HeaderOverlay)
    assert.equal(styles.searchResultsCard.position, undefined)
    assert.equal(elements(panel).find(el => el.type === "Scroll").props.keyboardShouldPersistTaps, "handled")
    elements(panel).find(el => el.props.accessibilityLabel === "Result").props.onPress()
    assert.equal(pushed, "/product/9"); assert.equal(closed, 3)
})

test("journal counts inclusive calendar days across leap days, DST and year boundaries", () => {
    const dates = load("screens/chat/companion-timezones.ts")
    const { recentReviewRange, selectReviewDay, exclusiveReviewEnd, lastReviewDay } = load("screens/chat/companion-review-range.ts", { "@/screens/chat/companion-timezones": dates })
    assert.deepEqual(recentReviewRange("2026-01-02", 7), { start: "2025-12-27", end: "2026-01-02" })
    assert.equal(exclusiveReviewEnd(recentReviewRange("2024-02-29", 1)), "2024-03-01")
    const range = recentReviewRange("2026-03-08", 30)
    assert.equal(range.start, "2026-02-07")
    const end = lastReviewDay(range.start)
    assert.equal(exclusiveReviewEnd(selectReviewDay(range, "end", end)), "2026-05-08")
    assert.strictEqual(selectReviewDay(range, "end", "2026-05-08"), range)
    assert.strictEqual(selectReviewDay(range, "end", "2026-02-06"), range)
    assert.deepEqual(selectReviewDay(range, "start", "2026-11-25"), { start: "2026-11-25", end: "2026-11-25" })
})

test("calendar month and Monday-first weekdays follow the rendered language, independent of global locale", () => {
    let language = "en", offset = 0
    const { MentorCalendarHeader } = load("screens/chat/mentor-calendar-header.tsx", {
        "react-native": rn, "@/providers/language-provider": { useLanguage: () => ({ language }) },
        "@/screens/chat/mentor-question-icon": { MentorQuestionIcon: "Icon" },
    })
    const render = () => elements(MentorCalendarHeader({ month: new Date(2026, 10, 1), addMonth: n => { offset += n }, disableArrowRight: true }))
    const labels = () => render().filter(el => el.type === "Text").map(el => el.props.children)
    assert.deepEqual(labels(), ["November 2026", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    language = "kz"
    assert.deepEqual(labels(), ["Қараша 2026", "Дс", "Сс", "Ср", "Бс", "Жм", "Сб", "Жс"])
    const arrows = render().filter(el => el.type === "Pressable")
    arrows[0].props.onPress(); assert.equal(offset, -1)
    assert.equal(arrows[1].props.disabled, true)
    language = "ru"
    assert.equal(labels()[1], "Пн")
})
