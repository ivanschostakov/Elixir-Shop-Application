const assert = require("node:assert/strict")
const test = require("node:test")
const loadTs = require("./load-ts.cjs")
const { createLoyaltySession } = loadTs("services/loyalty-session.ts")
const tick = () => new Promise(resolve => setImmediate(resolve))
const offer = { offer_partner: true, own_code_eligible: false, own_promo_code: "LEGACY", company_promo_code: "FIRM" }
const both = { ...offer, own_code_eligible: true }
const accepted = { ...both, offer_partner: false, company_promo_code: null }
function deferred() {
    let resolve, reject
    const promise = new Promise((yes, no) => { resolve = yes; reject = no })
    return { promise, resolve, reject }
}

test("canonical authenticated milestone POSTs use the existing versioned users prefix", async () => {
    const posts = []
    const users = loadTs("services/api/users.ts", {
        "@/services/api/constants": loadTs("services/api/constants.ts", { "@/config/env": { API_BASE_URL: "https://example.test/api" } }),
        "@/services/api/client": { apiPost: (...args) => { posts.push(args); return both } },
    })
    assert.equal(await users.checkMyMilestones(), both)
    assert.equal(await users.acceptMyPartnerOffer(), both)
    assert.deepEqual(posts, ["check", "accept"].map(op => ["/v1/users/me/referral-profile/milestones/" + op, null]))
})

test("verification authenticates without a signup choice even with a legacy server flag", async () => {
    const calls = [], cached = []
    const auth = loadTs("services/auth/auth.ts", {
        "@/services/api/constants": { ENDPOINTS: { AUTH: "/v1/auth" } }, "@/utils/errors": {},
        "@/services/api/client": { apiPost: async path => {
            calls.push(path)
            return { user: { id: 12, program_selection_required: true }, session_id: 4 }
        } },
        "@/services/auth/session": { setAuthTokens() {}, cacheAuthUser: user => cached.push(user) },
    })
    const user = await auth.verifyRegistration({ code: "123456" })
    assert.deepEqual(calls, ["/v1/auth/register/verify"])
    assert.equal(user.id, 12)
    assert.equal(user.programSelectionRequired, undefined)
    assert.deepEqual(cached, [user])
})

test("event bursts join one check; payments during that check produce one trailing read", async () => {
    const first = deferred()
    let calls = 0
    const session = createLoyaltySession({ check: () => ++calls === 1 ? first.promise : Promise.resolve(both) }, () => true)
    const checking = session.check()
    assert.equal(session.check(), checking)
    assert.equal(session.check("paid"), checking)
    session.check("paid")
    assert.equal(calls, 1)
    first.resolve(offer)
    await tick()
    assert.equal(calls, 2)
    assert.equal(session.snapshot().data, both)
})

test("only an owned, confirmed paid order triggers a milestone read, not a draft, pending or failed payment", () => {
    const { confirmedPaidOrderId } = loadTs("screens/payment/payment-state.ts")
    const order = { id: 14, user_id: 1, payment_status: "pending", is_paid: false }
    assert.equal(confirmedPaidOrderId(1, order, null), null)
    for (const status of ["draft", "pending", "error", "canceled", "refunded", "hold", "partial"]) {
        const is_paid = ["refunded", "partial"].includes(status)
        assert.equal(confirmedPaidOrderId(1, order, { order_id: 14, payment_status: status, is_paid }), null)
    }
    const paid = { order_id: 14, payment_status: "paid" }
    assert.equal(confirmedPaidOrderId(1, order, paid), 14)
    assert.equal(confirmedPaidOrderId(1, { ...order, is_paid: true }, null), 14)
    assert.equal(confirmedPaidOrderId(2, order, paid), null)
    assert.equal(confirmedPaidOrderId(1, order, { ...paid, order_id: 15 }), null)
})

test("one accept waits for a check; failures and pending responses retain the last confirmed state", async () => {
    let response = offer, accepts = 0, consent = deferred()
    const session = createLoyaltySession({
        check: async () => response,
        accept: () => { accepts++; return consent.promise },
    }, () => true)
    await session.check()
    session.check()
    const saving = session.accept()
    assert.equal(session.accept(), saving)
    await tick()
    assert.equal(session.snapshot().pending, "accept")
    session.check()
    consent.reject(Error("offline"))
    await saving
    assert.equal(accepts, 1)
    assert.deepEqual(session.snapshot(), { data: offer, pending: null, error: "accept", programRevision: 0 })
    response = null
    await session.check()
    assert.equal(session.snapshot().data, offer)
    assert.equal(session.snapshot().error, "check")
    consent = deferred()
    consent.resolve(accepted)
    await session.accept()
    assert.deepEqual(session.snapshot(), { data: accepted, pending: null, error: null, programRevision: 1 })
})

test("old results, queued accepts and trailing checks cannot act after logout", async () => {
    let active = true, calls = 0, accepts = 0
    const late = deferred()
    const session = createLoyaltySession({ check: () => ++calls === 1 ? offer : late.promise, accept: () => { accepts++ } }, () => active)
    await session.check()
    session.check()
    session.check("paid")
    const waiting = session.accept()
    active = false
    late.resolve(both)
    await waiting
    await session.accept()
    assert.equal(calls, 2)
    assert.equal(accepts, 0)
    assert.equal(session.snapshot().data, offer)
})

// Render the session hook with its real requests coordinator, storage keys and native alert queue.
function mount({ stored = new Map(), os = "ios" } = {}) {
    const alerts = [], listeners = new Set(), slots = []
    let index = 0, effects, user = 1, sessionId = 10, path = "/", value, reads = 0, accepts = 0, response = offer
    const app = { currentState: "active", addEventListener: (_, f) => { listeners.add(f); return { remove: () => listeners.delete(f) } } }
    const native = { AppState: app, Platform: { OS: os }, Alert: { alert: (title, body, buttons) => alerts.push({ title, body, buttons }) } }
    const notices = loadTs("services/notifications/startup-notices.ts", { "react-native": native })
    function changed(slot, deps) {
        return !slot || deps.some((v, i) => v !== slot.deps[i])
    }
    const { useLoyaltyMilestones: runHook } = loadTs("providers/use-loyalty-milestones.ts", {
        react: {
            useRef(initial) { const i = index++; return slots[i] ??= { current: initial } },
            useMemo(f, deps) {
                const i = index++
                if (changed(slots[i], deps)) slots[i] = { value: f(), deps }
                return slots[i].value
            },
            useEffect(f, deps) {
                const i = index++
                if (changed(slots[i], deps)) effects.push(() => { slots[i]?.cleanup?.(); slots[i] = { deps, cleanup: f() } })
            },
            useSyncExternalStore: (_, get) => get(),
        },
        "react-native": native, "expo-secure-store": {
            getItemAsync: async k => stored.get(k), setItemAsync: async (k, v) => stored.set(k, v),
        },
        "@/services/commerce-account": { commerceAccountId: () => user },
        "@/services/auth/session": { getAuthTokens: () => ({ sessionId }) },
        "@/services/api/users": { checkMyMilestones: async () => { reads++; return response }, acceptMyPartnerOffer: async () => { accepts++; return accepted } },
        "@/services/notifications/startup-notices": notices,
        "@/services/loyalty-session": loadTs("services/loyalty-session.ts"),
        "@/constants/routes": { ROUTES: { profile: "/profile", profileDiscounts: "/profile-discounts" } },
        "@/i18n/translations": { translate: k => k },
    })
    async function render() {
        index = 0; effects = []
        value = runHook(user, sessionId, path)
        effects.forEach(f => f())
        await tick()
    }
    return { render, alerts, notices, reads: () => reads, accepts: () => accepts, value: () => value,
        route: p => { path = p }, account: n => { user = n; sessionId++ }, respond: v => { response = v },
        appState(s) { app.currentState = s; for (const f of listeners) f(s) } }
}

test("native auth, foreground and entering profile/discounts trigger checks, ordinary routes do not", async () => {
    const h = mount()
    h.route("/profile")
    await h.render()
    assert.equal(h.reads(), 1)
    h.route("/discover"); await h.render()
    assert.equal(h.reads(), 1)
    h.route("/profile-discounts"); await h.render()
    h.appState("background"); h.appState("active"); h.appState("active")
    await tick()
    assert.equal(h.reads(), 3)
    h.account(undefined); await h.render()
    h.appState("background"); h.appState("active")
    assert.equal(h.reads(), 3)
    const web = mount({ os: "web" })
    await web.render()
    assert.equal(web.reads(), 0)
})

test("welcome, partner and qualified code alerts take turns; Later survives relaunch but not account changes", async () => {
    const stored = new Map(), h = mount({ stored })
    void h.notices.queueStartupNotice(async () => { await h.notices.presentStartupNotice("welcome", "", ["OK"]) })
    await h.render()
    await h.render()
    assert.deepEqual(h.alerts.map(a => a.title), ["welcome"])
    h.alerts[0].buttons[0].onPress()
    await tick()
    assert.equal(h.alerts[1].title, "milestone.offerTitle")
    assert.match(h.alerts[1].body, /FIRM/)
    h.alerts[1].buttons[0].onPress()
    await tick()
    assert.equal(h.accepts(), 0)
    assert.equal(h.value().data.own_promo_code, "LEGACY")
    assert.equal(h.alerts.length, 2)
    const again = mount({ stored })
    again.respond(both)
    await again.render(); await again.render()
    assert.deepEqual(again.alerts.map(a => a.title), ["milestone.codeTitle"])
    again.alerts[0].buttons[0].onPress()
    await tick()
    again.account(2)
    await again.render(); await again.render()
    assert.equal(again.alerts[1].title, "milestone.offerTitle")
    assert.equal(again.alerts.length, 2)
    again.alerts[1].buttons[1].onPress()
    await tick()
    assert.equal(again.accepts(), 1)
    assert.equal(again.alerts[2].title, "milestone.codeTitle")
    again.alerts[2].buttons[0].onPress()
    await again.render()
    assert.equal(again.value().data.offer_partner, false)
    assert.equal(again.alerts.length, 3)
})
