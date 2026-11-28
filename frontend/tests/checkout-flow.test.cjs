const assert = require("node:assert/strict")
const { setImmediate } = require("node:timers")
const test = require("node:test")
const load = require("./load-ts.cjs")

const noop = () => {}
const identity = value => value
const tick = () => new Promise(resolve => setImmediate(resolve))
function deferred() {
    let resolve
    const promise = new Promise(done => { resolve = done })
    return { promise, resolve }
}
const routes = { checkout: "/checkout", payment: "/payment", profileHistory: "/history", discover: "/shop" }
const routeParams = load("utils/route-params.ts")
const constants = load("screens/checkout/checkout-screen.constants.ts")
const utils = load("screens/checkout/checkout-screen.utils.ts", {
    "@/screens/checkout/checkout-screen.constants": constants,
    "@/services/api/delivery": {}, "@/utils/order-drafts": {}, "@/utils/errors": {},
    "@/utils/formatting": { formatMoney: String }, "@/utils/route-params": routeParams,
})
const basket = {
    id: 11, currency: "RUB", grand_total: "100", total_amount: "100", delivery_total: "0",
    items: [{ id: 3, variant_id: 4, quantity: 1, unit_price: "100", line_total: "100", product: { id: 5, name: "Item" }, variant: {} }],
    recipient: { id: 9, name: "Anna", surname: "Test", phone: "+79111111111", email: "recipient@example.test" },
    delivery_address: { id: 7, full_address: "Test address" },
}
const draft = utils.buildCheckoutDraftFromBasket(basket)
const paymentState = load("screens/payment/payment-state.ts")
const historyUtils = load("screens/profile/profile-history-screen.utils.ts")
class ApiError extends Error {}

// Run screen effects with persistent hook slots, without an Expo bridge or a live payments endpoint.
function screenHooks() {
    const slots = []
    let index, effects
    const same = (a, b) => a && b && a.length === b.length && a.every((v, i) => Object.is(v, b[i]))
    const hooks = {
        useState(initial) {
            const i = index++
            if (!(i in slots)) slots[i] = typeof initial === "function" ? initial() : initial
            return [slots[i], update => { slots[i] = typeof update === "function" ? update(slots[i]) : update }]
        },
        useRef(initial) { return slots[index++] ??= { current: initial } },
        useMemo(fn, deps) {
            const i = index++
            if (!same(slots[i]?.deps, deps)) slots[i] = { deps, value: fn() }
            return slots[i].value
        },
        useCallback(fn, deps) { return hooks.useMemo(() => fn, deps) },
        useEffect(fn, deps) {
            const i = index++
            if (!same(slots[i]?.deps, deps)) effects.push(() => {
                slots[i]?.cleanup?.()
                slots[i] = { deps, cleanup: fn() }
            })
        },
    }
    return { hooks, render(screen) {
        index = 0
        effects = []
        const view = screen()
        for (const run of effects) run()
        return view
    }, unmount() { for (const slot of slots) slot?.cleanup?.() } }
}

function nodes(root) {
    if (root == null || typeof root === "boolean") return []
    if (Array.isArray(root)) return root.flatMap(nodes)
    return [root, ...(root.props ? nodes(root.props.children) : [])]
}

function mount(t, page, { guest = false, platform = "ios", params = {}, status, createError, onPost,
    orderFields, beforeCreate, readOrder, promoBinding, translate = identity } = {}) {
    const calls = [], pushes = [], links = [], alerts = []
    const { hooks, render, unmount } = screenHooks()
    t.after(unmount)
    const appState = { currentState: "active" }
    const email = load("screens/checkout/guest-checkout-email.ts")
    const order = { ...draft, id: 42, order_number: "A42", checkout_snapshot: {}, payment_method: params.paymentMethod ?? "sbp", ...orderFields }
    const create = async (kind, body) => {
        calls.push([kind, body])
        if (createError) throw createError
        await beforeCreate
        return kind === "guest" ? { order } : order
    }
    const api = load("services/api/payments.ts", {
        "@/services/api/request-deadline": load("services/api/request-deadline.ts"),
        "@/services/api/constants": { ENDPOINTS: { PAYMENTS: "/payments" } },
        "@/services/api/client": {
            ApiError,
            apiGet: async (path, query) => { calls.push([path, query]); return status() },
            apiPost: async (path, body) => { calls.push([path, body]); return onPost?.() },
        },
    })
    const native = Object.fromEntries(["ActivityIndicator", "Image", "Modal", "Pressable", "ScrollView", "Text", "TextInput", "View"].map(k => [k, k]))
    let footer, tree
    const mocks = {
        react: hooks,
        "react-native": { ...native, FlatList: "FlatList", useWindowDimensions: () => ({ width: 390 }),
            AppState: appState, Platform: { OS: platform }, Keyboard: {}, StyleSheet: { create: identity },
            Alert: { alert: (...args) => alerts.push(args) },
            Linking: { openURL: async url => { links.push(url); throw new Error("No bank app") } },
            Animated: { Value: class { stopAnimation() {} setValue() {} interpolate() {} }, View: "AnimatedView", timing: () => ({ start: noop }) },
            Easing: { out: identity },
        },
        "expo-router": { useLocalSearchParams: () => params, useFocusEffect: fn => hooks.useEffect(fn, [fn]),
            router: { push: route => pushes.push(route), replace: route => pushes.push(route), setParams: patch => Object.assign(params, patch) } },
        "expo-clipboard": {}, "lottie-react-native": "Lottie",
        "@react-native-picker/picker": { Picker: { Item: "Item" } },
        "react-native-safe-area-context": { useSafeAreaInsets: () => ({ top: 0, bottom: 0 }) },
        "@/constants/routes": { ROUTES: routes }, "@/constants/stickers": { STICKERS: { cherryCongrats: {}, orderHistoryEmpty: {} } },
        "@/hooks/basket/use-basket": { useBasket: () => ({ basket }) },
        "@/hooks/basket/basket-store": { clearBasketSnapshot: noop },
        "@/hooks/order-draft/use-order-draft": { useOrderDraft: () => ({ orderDraft: draft }) },
        "@/providers/auth-provider": { useAuth: () => ({ isReady: true, isAuthenticated: !guest, acceptSession: noop }) },
        "@/providers/language-provider": { useLanguage: () => ({ t: translate, language: "ru" }) },
        "@/providers/theme-provider": { useTheme: () => ({ palette: {} }) },
        "@/hooks/use-theme-styles": { useThemeStyles: () => ({}) },
        "@/components/templates/screen-template.hooks": { useApplyScreenTemplate: (_, chrome) => { footer = chrome?.slots?.footer } },
        "@/hooks/basket/use-basket-mutations": { useBasketMutations: () => ({}) },
        "@/hooks/basket/use-order-benefits": { useOrderBenefits: () => ({ data: guest ? null : { stacked_discount_options: [] } }) },
        "@/hooks/products/use-infinite-product-catalog": { useInfiniteProductCatalog: () => ({ products: [] }) },
        "@/hooks/recommendations/use-recommendations": { useRecommendations: () => ({ products: [] }) },
        "@/hooks/shared/use-async-data": { useAsyncData: () => ({ data: null, reload: noop }) },
        "@/screens/checkout/checkout-screen.constants": constants, "@/screens/checkout/checkout-screen.utils": utils,
        "@/screens/checkout/guest-checkout-email": email,
        "@/screens/checkout/use-checkout-recipient-selection": { useCheckoutRecipientSelection: (_, recipient) => ({ recipient }) },
        "@/services/api/client": { ApiError }, "@/services/api/payments": api,
        "@/services/api/guest": { createGuestOrder: async body => create("guest", body), isGuestPhoneExistsError: () => false },
        "@/services/api/orders": { createOrder: async body => create("member", body), getOrder: async () => readOrder?.() ?? order },
        "@/services/auth/session": { getAuthTokens: () => null },
        "@/services/guest-cart": { clearGuestCart: async () => {} },
        "@/services/notifications/startup-notices": { queueStartupNotice: noop },
        "@/screens/payment/payment-state": paymentState,
        "@/screens/profile/profile-history-screen.utils": historyUtils, "./profile-history-screen.utils": historyUtils,
        "./profile-history-screen.styles": {}, "react-native-calendars": { LocaleConfig: { locales: {} } },
        "@/hooks/shared/use-paginated-data": { usePaginatedData: () => ({ items: [order], reload: noop }) },
        "@/components/content/recent-order-drafts-rail.utils": { getModeBadgeStyle: noop },
        "@/utils/quoted-item-price": load("utils/quoted-item-price.ts"),
        "@/utils/discount-display": { confirmedBalanceAmount: () => null, orderDiscountRows: () => [] },
        "@/utils/errors": { getErrorMessage: e => e.message, showBackendErrorAlert: noop },
        "@/utils/route-params": routeParams, "@/theme/spacing": { spacing: {} },
    }
    for (const path of [
        "components/content/content-rail", "components/content/content.styles", "components/footer/sticky-footer.styles",
        "components/platform/app-form-layout", "components/platform/app-picker", "hooks/basket/basket-draft-editing-store",
        "hooks/delivery/delivery-address-selection-store", "hooks/delivery/delivery-country-selection-store",
        "hooks/delivery/delivery-point-selection-store", "hooks/order-draft/order-draft-store",
        "screens/cart/cart-screen.utils", "screens/cart/order-promo", "screens/cart/confirm-promo-binding", "screens/checkout/checkout-address-picker",
        "screens/checkout/checkout-screen.styles", "screens/payment/payment-screen.styles", "components/platform/app-calendar",
        "components/content/content-tab-bar", "components/content/empty-state", "components/templates/catalog-template",
        "services/api/basket", "services/api/benefits", "services/api/order-drafts", "services/api/users", "services/notifications/order-status-notifications",
    ]) mocks["@/" + path] = {}
    if (promoBinding) {
        const getProfile = () => {}
        let profile = { reward_program: "bonus", referrer_promo_code: null }
        mocks["@/services/api/users"] = { getMyReferralProfile: getProfile,
            bindMyReferrerCode: async code => { calls.push(["bind", code]); return { referrer_promo_code: "Хрюн_Слим" } } }
        mocks["@/screens/cart/confirm-promo-binding"] = { confirmPromoBinding: async () => true }
        mocks["@/hooks/shared/use-async-data"] = { useAsyncData: ({ fetcher }) => fetcher === getProfile
            ? { data: profile, setData: update => { profile = update(profile) }, reload: noop }
            : { data: null, reload: noop } }
    }
    const screen = load(page === "history" ? "screens/profile/profile-history-screen.tsx"
        : "screens/" + page + "/" + page + "-screen.tsx", mocks).default
    return {
        render() { tree = render(screen) },
        elements: () => nodes(tree),
        historyCard() {
            const list = nodes(tree).find(n => n.type === "FlatList")
            const card = list.props.renderItem({ item: list.props.data[0] }).props.children
            return nodes(render(() => card.type(card.props)))
        },
        cta() {
            const buttons = nodes(footer).filter(n => n.props?.accessibilityRole === "button")
            assert.equal(buttons.length, 1, "one checkout footer action")
            return buttons[0].props
        },
        calls, pushes, links, alerts, email, appState,
    }
}

test("applying a code directly in checkout binds before choosing payment or creating an order", async t => {
    const app = mount(t, "checkout", { promoBinding: true })
    const field = () => app.elements().find(n => n.props?.placeholder === "checkout.promoCodePlaceholder")
    app.render()
    field().props.onChangeText("хрюн_слим")
    app.render()
    app.cta().onPress()
    await tick()
    app.render()
    assert.deepEqual(app.calls, [["bind", "хрюн_слим"]])
    assert.equal(field().props.editable, false)
    assert.equal(field().props.value, "Хрюн_Слим")
    assert.deepEqual(app.pushes, [])
})

test("native checkout waits for the method alert, can be cancelled, and proceeds only once", t => {
    for (const platform of ["android", "ios"]) for (const guest of [true, false]) {
        const app = mount(t, "checkout", { guest, platform })
        app.render()
        assert.equal(app.elements().some(n => n.props?.accessibilityRole === "radio"), false)
        assert.deepEqual(app.pushes, [])
        assert.equal(app.cta().accessibilityLabel, "checkout.payCta")
        const input = app.elements().find(n => n.props?.accessibilityLabel === "payment.recoveryEmail")
        if (guest) {
            for (const invalid of ["", "buyer @example.test"]) {
                input.props.onChangeText(invalid)
                app.render()
                app.cta().onPress()
                app.render()
                assert.deepEqual(app.pushes, [])
                assert.ok(app.elements().includes("auth.error.invalidEmail"))
                assert.equal(app.email.getGuestCheckoutEmail(), "")
            }
            input.props.onChangeText(" buyer@example.test ")
            app.render()
        } else {
            assert.equal(input, undefined)
            app.email.setGuestCheckoutEmail("old@example.test")
        }
        assert.equal(app.alerts.length, 0)
        app.cta().onPress()
        app.cta().onPress()
        assert.equal(app.alerts.length, 1)
        assert.equal(app.alerts[0][0], "checkout.paymentMethodTitle")
        const buttons = app.alerts[0][2]
        assert.deepEqual(buttons.map(b => b.text), ["checkout.paymentMethodCancel", "payment.methodLaterTitle", "payment.methodSbpTitle"])
        buttons[0].onPress()
        app.cta().onPress()
        app.alerts[1][3].onDismiss()
        assert.deepEqual(app.pushes, [])
        assert.deepEqual(app.calls, [])
        const method = guest ? "later" : "sbp"
        app.cta().onPress()
        const button = app.alerts[2][2][guest ? 1 : 2]
        button.onPress()
        button.onPress()
        app.cta().onPress()
        assert.deepEqual(app.pushes, [{ pathname: routes.payment, params: { paymentMethod: method } }])
        assert.equal(app.email.getGuestCheckoutEmail(), guest ? "buyer@example.test" : "")
    }
})

test("web checkout keeps an inline method selector", t => {
    const app = mount(t, "checkout", { platform: "web" })
    app.render()
    const radios = app.elements().filter(n => n.props?.accessibilityRole === "radio")
    assert.equal(radios.length, 2)
    radios[1].props.onPress()
    app.render()
    app.cta().onPress()
    assert.deepEqual(app.pushes, [{ pathname: routes.payment, params: { paymentMethod: "later" } }])
    assert.deepEqual(app.alerts, [])
})

test("new checkout schedules work on order creation; background/foreground recovery only reads that order", async t => {
    t.mock.timers.enable({ apis: ["setTimeout"] })
    for (const [guest, method] of [[true, "later"], [false, "sbp"]]) {
        const state = { order_id: 42, payment_method: method, payment_status: "pending", checkout_progress: "processing" }
        let failRead = true
        const app = mount(t, "payment", { guest, params: { paymentMethod: method }, status: () => {
            if (failRead) { failRead = false; throw new TypeError("Lost connection") }
            return { ...state }
        } })
        app.email.setGuestCheckoutEmail("Buyer@example.test")
        app.render()
        await tick()
        app.render()
        assert.equal(app.calls[0][0], guest ? "guest" : "member")
        const body = app.calls[0][1]
        assert.equal(body.automatic_checkout, true)
        assert.equal(body.payment_method, method)
        if (guest) {
            assert.equal(body.buyer_email, "buyer@example.test")
            assert.equal(body.recipient.email, basket.recipient.email)
            assert.equal(app.email.getGuestCheckoutEmail(), "")
        }
        const query = { order_id: 42, automatic_checkout: true, accept_pending_amount: true }
        assert.deepEqual(app.calls.slice(1), [["/payments/status", query]])
        assert.equal(app.cta().accessibilityLabel, "route.profileHistory")
        app.appState.currentState = "background"
        t.mock.timers.tick(30_000)
        await tick()
        assert.equal(app.calls.length, 2)
        app.appState.currentState = "active"
        t.mock.timers.tick(30_000)
        await tick()
        app.render()
        Object.assign(state, { checkout_progress: null, ms_reservation_confirmed: true, invoice_id: "ready",
            qr_url: method === "sbp" ? "https://example.test/pay" : null })
        t.mock.timers.tick(30_000)
        await tick()
        app.render()
        assert.deepEqual(app.calls.slice(1), Array.from({ length: 3 }, () => ["/payments/status", query]))
        if (guest) {
            assert.ok(app.elements().includes("payment.pendingLaterMessage"))
            assert.equal(app.cta().accessibilityLabel, "route.profileHistory")
        } else {
            assert.equal(app.cta().accessibilityLabel, "payment.tapToPayPlaceholder")
            assert.equal(app.cta().disabled, false)
            app.cta().onPress()
            await tick()
            assert.deepEqual(app.links, [state.qr_url])
            assert.ok(app.alerts.flat().includes("payment.bankLinkFailed"))
        }
    }
})

test("a fresh order is not submitted again even when the status read has no job marker yet", async t => {
    t.mock.timers.enable({ apis: ["setTimeout"] })
    const app = mount(t, "payment", { params: { paymentMethod: "sbp" }, status: () => ({
        order_id: 42, payment_method: "sbp", payment_status: "draft", is_paid: false,
    }) })
    app.render()
    await tick()
    app.render()
    t.mock.timers.tick(30_000)
    await tick()
    app.render()
    assert.deepEqual(app.calls.map(([path]) => path), ["member", "/payments/status", "/payments/status"])
    assert.ok(app.calls.slice(1).every(([, query]) => query.order_id === 42))
})

test("unknown create outcome directs the buyer to history without offering another submit", async t => {
    const app = mount(t, "payment", { params: { paymentMethod: "sbp" }, createError: new TypeError("Disconnected") })
    app.render()
    await tick()
    app.render()
    assert.ok(app.elements().includes("payment.checkHistoryOnDisconnect"))
    assert.notEqual(app.cta().accessibilityLabel, "payment.retry")
    app.cta().onPress()
    await tick()
    app.render()
    assert.deepEqual(app.calls.map(c => c[0]), ["member"])
})

test("history adopts an old unscheduled draft once, but stored jobs, review and bank failures never auto-submit", async t => {
    t.mock.timers.enable({ apis: ["setTimeout"] })
    for (const scenario of ["legacy", "job", "review", "retry", "no retry"]) {
        const status = {
            order_id: 42, payment_method: "sbp",
            payment_status: scenario.includes("retry") ? "error" : "draft",
            checkout_progress: scenario === "job" ? "processing" : scenario === "review" ? "needs_review" : null,
            can_retry: scenario === "retry" || scenario === "review",
        }
        const app = mount(t, "payment", { params: { orderId: "42" }, status: () => status,
            onPost: () => ({ ...status, checkout_progress: "processing" }) })
        app.render()
        await tick()
        app.render()
        await tick()
        app.render()
        const paths = () => app.calls.map(c => c[0])
        assert.deepEqual(paths(), scenario === "legacy" ? ["/payments/status", "/payments/create"] : ["/payments/status"])
        if (scenario === "review") assert.ok(app.elements().includes("payment.checkoutReview"))
        if (scenario === "retry") {
            assert.equal(app.cta().accessibilityLabel, "payment.retry")
            app.cta().onPress()
            app.cta().onPress()
            await tick()
        } else assert.notEqual(app.cta().accessibilityLabel, "payment.retry")
        const posts = app.calls.filter(([path]) => path === "/payments/create")
        assert.equal(posts.length, Number(scenario === "legacy" || scenario === "retry"))
        for (const [, body] of posts) assert.deepEqual(body, { order_id: 42, payment_method: "sbp", automatic_checkout: true })
    }
})

test("all three checkout dictionaries have distinct recovery guidance and no manual invoice instructions", () => {
    const { translate } = load("i18n/translations.ts")
    for (const [index, lang] of ["ru", "en", "kz"].entries()) {
        assert.equal(translate("checkout.payCta", lang), ["Оформить", "Place order", "Тапсырыс беру"][index])
        for (const key of ["payment.checkoutReview", "payment.checkHistoryOnDisconnect", "payment.bankLinkFailed",
            "payment.pendingLaterTitle", "payment.pendingLaterMessage", "payment.tapToPayPlaceholder",
            "payment.settlementWaitingTimeout", "payment.invoiceStillPreparing", "payment.checkInvoice", "checkout.automaticBalanceHint"]) {
            const value = translate(key, lang)
            assert.ok(value && value !== key, key)
            if (lang !== "ru") assert.notEqual(value, translate(key, "ru"), key + " must not fall back to Russian")
            assert.doesNotMatch(value, /invoice|(?<![а-яё])сч[её]т|шот/i)
        }
        assert.match(translate("payment.bankLinkFailed", lang), /QR/)
        assert.doesNotMatch(translate("payment.checkoutReview", lang), /поддержк|support|қолдау/i)
        assert.match(translate("payment.pendingLaterMessage", lang), /менеджер|manager/i)
        assert.match(translate("payment.pending", lang), /менеджер|manager/i)
        assert.match(translate("payment.checkHistoryOnDisconnect", lang), /истори|history|тарих/i)
    }
})

const { translate } = load("i18n/translations.ts")
const issue = {
    code: "MS_429", message: "МойСклад временно ограничил число запросов (429). Не удалось получить страну для заказа.",
    retrying: true, retry_until: "2026-11-28T14:37:00Z",
}
const reason = issue.code + ": " + issue.message

test("only a received order number unlocks history and the processing notification, even before the first status read", async t => {
    const receipt = deferred(), status = deferred()
    const app = mount(t, "payment", {
        params: { paymentMethod: "later" }, beforeCreate: receipt.promise, orderFields: { status_code: "processing" },
        status: () => status.promise, translate: key => translate(key, "ru"),
    })
    const notice = "Заказ обрабатывается. Вы можете покинуть эту страницу. Мы отправим уведомление, когда обработка завершится."
    app.render()
    app.render()
    assert.equal(app.cta().disabled, true)
    assert.ok(!app.elements().includes(notice))
    assert.ok(!app.elements().includes("#A42"))
    receipt.resolve()
    await tick()
    app.render()
    assert.ok(app.elements().includes("#A42"))
    assert.ok(app.elements().includes(notice))
    assert.equal(app.cta().disabled, false)
    app.cta().onPress()
    assert.deepEqual(app.pushes, [routes.profileHistory])
    status.resolve({ order_id: 42, status_code: "processing", payment_status: "pending" })
    await tick()
    app.render()
    assert.deepEqual(app.calls.map(c => c[0]), ["member", "/payments/status"])
})

test("history cards keep the number, untruncated reason and code together in every locale", t => {
    assert.ok(historyUtils.getStatusCodesForBucket("active").includes("processing"))
    assert.ok(historyUtils.getStatusCodesForBucket("active").includes("checkout_failed"))
    for (const lang of ["ru", "en", "kz"]) for (const code of ["processing", "checkout_failed"]) {
        const tr = key => translate(key, lang)
        const problem = { ...issue, retrying: code === "processing" }
        const app = mount(t, "history", { orderFields: { status_code: code, checkout_issue: problem }, translate: tr })
        app.render()
        const card = app.historyCard()
        assert.ok(card.includes("A42")) // The leading # is a separate Text child in the list.
        const reasonText = card.find(n => n.type === "Text" && n.props.children === reason)
        assert.ok(reasonText)
        assert.equal(reasonText.props.numberOfLines, undefined)
        const button = card.find(n => n.props?.accessibilityRole === "button")
        assert.ok(button.props.accessibilityLabel.includes("#A42"))
        assert.ok(button.props.accessibilityLabel.includes(reason))
        for (const key of [historyUtils.ORDER_STATUS_LABEL_KEYS[code], historyUtils.ORDER_STATUS_MESSAGE_KEYS[code]]) {
            assert.ok(card.includes(tr(key)))
            if (lang !== "ru") assert.notEqual(tr(key), translate(key, "ru"))
        }
        assert.ok(!card.includes(tr("profile.history.status.created")))
        assert.equal(card.includes(historyUtils.checkoutRetryMessage(issue, tr)), problem.retrying)
        button.props.onPress()
        assert.deepEqual(app.pushes, [{ pathname: routes.payment, params: { orderId: "42" } }])
    }
})

test("reopened processing orders only read status: transient failures and retries never post and terminal reasons persist", async t => {
    t.mock.timers.enable({ apis: ["setTimeout"] })
    let read = 0
    const app = mount(t, "payment", {
        params: { orderId: "42" }, orderFields: { status_code: "processing", checkout_issue: issue },
        status: () => {
            if (++read === 1) throw new TypeError("lost connection")
            if (read === 2) return { order_id: 42, payment_status: "draft" }
            return { order_id: 42, payment_status: "error", can_retry: true, status_code: "checkout_failed",
                checkout_issue: { ...issue, retrying: false } }
        },
    })
    app.render()
    await tick()
    app.render()
    await tick()
    app.render()
    for (let i = 0; i < 2; i++) {
        assert.ok(app.elements().includes("#A42"))
        assert.ok(app.elements().includes(reason))
        assert.ok(app.elements().includes("profile.history.statusMessage.processing"))
        assert.equal(app.cta().accessibilityLabel, "route.profileHistory")
        t.mock.timers.tick(30_000)
        await tick()
        app.render()
    }
    assert.ok(app.elements().includes(reason))
    assert.ok(app.elements().includes("profile.history.statusMessage.checkout_failed"))
    assert.ok(!app.elements().includes("profile.history.retryUntil"))
    assert.equal(app.cta().accessibilityLabel, "route.profileHistory")
    t.mock.timers.tick(3_600_000)
    await tick()
    assert.deepEqual(app.calls.map(c => c[0]), Array(3).fill("/payments/status"))
})

test("a completed status replaces stale processing and clears the reason without resubmitting", async t => {
    t.mock.timers.enable({ apis: ["setTimeout"] })
    for (const paymentHasStatusCode of [false, true]) {
        let state = "processing"
        const app = mount(t, "payment", {
            params: { orderId: "42" }, readOrder: () => ({ ...draft, id: 42, order_number: "A42", payment_method: "later",
                status_code: state, checkout_issue: state === "processing" ? issue : null }),
            status: () => ({ order_id: 42, payment_method: "later", payment_status: "pending", can_retry: false,
                ...(paymentHasStatusCode ? { status_code: state } : {}),
                checkout_progress: state === "processing" ? "processing" : null, checkout_issue: state === "processing" ? issue : null }),
        })
        app.render()
        await tick()
        app.render()
        await tick()
        app.render()
        assert.ok(app.elements().includes(reason))
        state = "created"
        t.mock.timers.tick(30_000)
        await tick()
        app.render()
        assert.ok(app.elements().includes("profile.history.status.created"))
        assert.ok(app.elements().includes("payment.pendingLaterTitle"))
        assert.ok(!app.elements().includes(reason))
        assert.deepEqual(app.calls.map(c => c[0]), ["/payments/status", "/payments/status"])
    }
})

test("payment-only lifecycle markers prevent legacy adoption and bank retry, even with stale draft flags", async t => {
    t.mock.timers.enable({ apis: ["setTimeout"] })
    for (const code of ["processing", "checkout_failed"]) {
        const app = mount(t, "payment", { params: { orderId: "42" }, orderFields: { status_code: "created" },
            status: () => ({ order_id: 42, status_code: code, payment_status: "draft", can_retry: true,
                checkout_issue: { ...issue, retrying: code === "processing" } }) })
        app.render()
        await tick()
        app.render()
        await tick()
        app.render()
        assert.ok(app.elements().includes("#A42"))
        assert.ok(app.elements().includes(reason))
        assert.ok(!app.elements().includes("profile.history.status.created"))
        assert.equal(app.cta().accessibilityLabel, "route.profileHistory")
        assert.deepEqual(app.calls.map(c => c[0]), ["/payments/status"])
    }
})

test("retry guidance uses the supplied cutoff, falls back to one hour, and disappears when retries stop", () => {
    for (const lang of ["ru", "en", "kz"]) {
        const tr = key => translate(key, lang)
        const cutoff = historyUtils.checkoutRetryMessage(issue, tr)
        assert.match(cutoff, /\d{1,2}:\d{2}/)
        assert.ok(!cutoff.includes("{time}"))
        for (const retry_until of [null, "not a timestamp"]) {
            assert.equal(historyUtils.checkoutRetryMessage({ ...issue, retry_until }, tr), tr("profile.history.retryWindow"))
        }
        assert.equal(historyUtils.checkoutRetryMessage({ ...issue, retrying: false }, tr), null)
        assert.equal(historyUtils.checkoutRetryMessage(null, tr), null)
    }
})

test("a confirmed created order without an invoice is not adopted as an unscheduled draft", async t => {
    const app = mount(t, "payment", {
        params: { orderId: "42" }, orderFields: { status_code: "created", payment_method: "later" },
        status: () => ({ order_id: 42, status_code: "created", payment_method: "later", payment_status: "pending" }),
    })
    app.render()
    await tick()
    app.render()
    await tick()
    app.render()
    assert.ok(app.elements().includes("payment.pendingLaterTitle"))
    assert.deepEqual(app.calls.map(c => c[0]), ["/payments/status"])
})

test("recovering a legacy status read can adopt once; losing the POST response never replays it", async t => {
    t.mock.timers.enable({ apis: ["setTimeout"] })
    let reads = 0
    const app = mount(t, "payment", {
        params: { orderId: "42" },
        status: () => {
            if (++reads === 1) throw Object.assign(new ApiError("Offline"), { status: 0 })
            if (reads === 2) throw Object.assign(new ApiError("Not ready"), {
                status: 409, body: { detail: { code: "settlement_pending" } },
            })
            return { order_id: 42, payment_status: "draft", payment_method: "sbp" }
        },
        onPost: () => { throw Object.assign(new ApiError("Gateway timeout"), { status: 504 }) },
    })
    app.render()
    await tick()
    app.render()
    await tick()
    app.render()
    for (let poll = 0; poll < 3; poll++) {
        t.mock.timers.tick(30_000)
        await tick()
        app.render()
    }
    assert.deepEqual(app.calls.map(c => c[0]), ["/payments/status", "/payments/status", "/payments/create",
        "/payments/status", "/payments/status"])
    assert.deepEqual(app.calls[2][1], { order_id: 42, payment_method: "sbp", automatic_checkout: true })
    assert.equal(app.cta().accessibilityLabel, "route.profileHistory")
})

test("legacy preparing is localized in history without displaying an unconfirmed total", t => {
    for (const lang of ["ru", "en", "kz"]) {
        const tr = key => translate(key, lang)
        const app = mount(t, "history", { orderFields: { status_code: "preparing", grand_total: "123.45" }, translate: tr })
        app.render()
        const card = app.historyCard()
        assert.ok(card.includes(tr("payment.preparingOrder")))
        assert.ok(!card.includes(tr("checkout.grandTotalLabel")))
    }
})
