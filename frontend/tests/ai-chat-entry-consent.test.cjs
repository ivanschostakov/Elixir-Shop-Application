const { test } = require("node:test")
const assert = require("node:assert/strict")
const loadTs = require("./load-ts.cjs")

function setup() {
    let state, previousDeps, cleanup, effect, focused = true, calls = 0
    let resolve, reject
    const pending = new Promise((yes, no) => { resolve = yes; reject = no })
    const exits = [], alerts = []
    class Declined extends Error {}
    const router = { canGoBack: () => true, back: () => exits.push("back"), replace: () => exits.push("home") }
    const { useAiChatEntryConsent } = loadTs("hooks/chat/use-ai-chat-entry-consent.ts", {
        react: {
            useState: () => [state, value => { state = value }],
            useEffect: (next, deps) => {
                if (!previousDeps || deps.some((value, i) => value !== previousDeps[i])) {
                    effect = next; previousDeps = deps
                }
            },
        },
        "@react-navigation/native": { useIsFocused: () => focused },
        "expo-router": { useRouter: () => router },
        "react-native": { Alert: { alert: (...args) => alerts.push(args) } },
        "@/constants/routes": { ROUTES: { home: "/" } },
        "@/providers/auth-provider": { useAuth: () => ({ user: { id: 1 } }) },
        "@/i18n/translations": { translate: key => key },
        "@/services/api/ai-data-consent": { AiConsentDeclinedError: Declined, ensureAiDataConsent: () => { calls++; return pending } },
        "@/utils/errors": { getErrorMessage: error => error.message },
    })
    return {
        render(active = true) {
            const allowed = useAiChatEntryConsent(active)
            if (effect) { cleanup?.(); cleanup = effect(); effect = null }
            return allowed
        },
        resolve, reject, Declined, exits, alerts,
        calls: () => calls,
        blur: () => { focused = false },
    }
}

const flush = () => new Promise(resolve => setImmediate(resolve))

test("entry stays closed until consent completes; support does not request consent", async () => {
    const s = setup()
    assert.equal(s.render(false), false)
    assert.equal(s.calls(), 0)
    assert.equal(s.render(), false)
    assert.equal(s.calls(), 1)
    s.resolve(); await flush()
    assert.equal(s.render(), true)
})

test("No exits without opening chat or displaying an error", async () => {
    const s = setup(); s.render()
    s.reject(new s.Declined()); await flush()
    assert.equal(s.render(), false)
    assert.deepEqual(s.exits, ["back"])
    assert.equal(s.alerts.length, 0)
})

test("failed consent save keeps chat closed and exits", async () => {
    const s = setup(); s.render()
    s.reject(new Error("offline")); await flush()
    assert.equal(s.render(), false)
    assert.deepEqual(s.exits, ["back"])
    assert.equal(s.alerts.length, 1)
})

test("leaving during consent ignores its late result", async () => {
    const s = setup(); s.render(); s.blur(); s.render()
    s.reject(new s.Declined()); await flush()
    assert.equal(s.render(), false)
    assert.equal(s.exits.length, 0)
})
