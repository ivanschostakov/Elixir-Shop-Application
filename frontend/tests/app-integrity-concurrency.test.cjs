const assert = require("node:assert/strict")
const test = require("node:test")
const loadTs = require("./load-ts.cjs")

function setup(t, overrides = {}) {
    const oldFetch = global.fetch
    const oldDev = global.__DEV__
    global.__DEV__ = false
    t.after(() => { global.fetch = oldFetch; global.__DEV__ = oldDev })
    const values = new Map()
    let challenge = 0, generated = 0, active = 0, peak = 0
    global.fetch = async url => new Response(JSON.stringify(url.endsWith("/challenge")
        ? { challenge: `challenge-${++challenge}` }
        : { key_id: "key-1", environment: "production" }), { status: 200 })
    const native = {
        isSupported: true,
        generateKeyAsync: async () => `key-${++generated}`,
        attestKeyAsync: async () => "attestation",
        generateAssertionAsync: async (_key, nonce) => {
            active++; peak = Math.max(peak, active)
            try {
                if (active > 1) throw Object.assign(new Error("Invalid input provided"), { code: "ERR_APP_INTEGRITY_INVALID_INPUT" })
                await new Promise(resolve => setTimeout(resolve, 5))
                return `assertion-${nonce}`
            } finally { active-- }
        },
        ...overrides,
    }
    const module = loadTs("services/app-integrity.ts", {
        "@expo/app-integrity": native,
        "expo-secure-store": {
            getItemAsync: async key => values.get(key) ?? null,
            setItemAsync: async (key, value) => values.set(key, value),
            deleteItemAsync: async key => values.delete(key),
        },
        "react-native": { Platform: { OS: "ios" } },
        "@/config/env": { API_BASE_URL: "https://example.test/api" },
        "@/services/auth/session": { getAuthTokens: () => ({ accessToken: "test" }) },
        "@/services/telegram/telegram-web-app": {},
    })
    return { ...module, stats: () => ({ generated, peak }) }
}

test("simultaneous mentor, chat and background requests do not rotate or race the iOS key", async t => {
    const api = setup(t)
    const results = await Promise.all(["ai-companion", "ai-chat:read", "ai-companion", "community:read"].map(action => api.getAppIntegrityHeaders(action)))
    assert.deepEqual(api.stats(), { generated: 1, peak: 1 })
    assert.equal(new Set(results.map(headers => headers["X-App-Integrity-Request-Hash"])).size, 4)
    assert.ok(results.every(headers => headers["X-App-Integrity-Key-Id"] === "key-1"))
})

test("a temporary Apple service error retries with the same key", async t => {
    const keys = []
    const api = setup(t, { attestKeyAsync: async key => {
        keys.push(key)
        if (keys.length === 1) throw Object.assign(new Error("Server unavailable"), { code: "ERR_APP_INTEGRITY_SERVER_UNAVAILABLE" })
        return "attestation"
    } })
    await api.getAppIntegrityHeaders("ai-companion")
    assert.deepEqual(keys, ["key-1", "key-1"])
    assert.equal(api.stats().generated, 1)
})

test("permanent native failure is not bypassed and does not poison the queue", async t => {
    let calls = 0
    const api = setup(t, { generateAssertionAsync: async () => {
        if (++calls === 1) throw Object.assign(new Error("Not supported"), { code: "ERR_APP_INTEGRITY_FEATURE_UNSUPPORTED" })
        return "assertion"
    } })
    await assert.rejects(api.getAppIntegrityHeaders("ai-companion"), api.AppIntegrityUnavailableError)
    const headers = await api.getAppIntegrityHeaders("ai-companion")
    assert.equal(headers["X-App-Integrity-Token"], "assertion")
    assert.equal(api.stats().generated, 1)
})

test("key reset waits for an in-flight assertion before deleting its key", async t => {
    const api = setup(t)
    const request = api.getAppIntegrityHeaders("ai-companion")
    const reset = api.resetAppIntegrityState()
    assert.equal((await request)["X-App-Integrity-Key-Id"], "key-1")
    await reset
    assert.equal((await api.getAppIntegrityHeaders("ai-companion"))["X-App-Integrity-Key-Id"], "key-2")
})

test("request client preserves device verification failures instead of inventing HTTP 503", async () => {
    class IntegrityError extends Error {}
    const failure = new IntegrityError("device failure")
    let fetched = false
    const api = loadTs("services/api/client.ts", {
        "@/services/api/constants": { API_BASE_URL: "https://example.test" },
        "@/services/app-integrity": { AppIntegrityUnavailableError: IntegrityError, getAppIntegrityHeaders: async () => { throw failure } },
        "@/services/auth/session": { getAuthTokens: () => null },
        "react-native": { Platform: { OS: "ios" } },
        "@/services/api/request-deadline": { RequestDeadlineError: class extends Error {}, fetchTextWithDeadline: async () => { fetched = true } },
        "@/screens/chat/companion-timezones": { deviceCompanionTimezone: () => "UTC" },
    })
    await assert.rejects(api.apiGet("/mentor", undefined, { appIntegrityAction: "ai-companion" }), error => error === failure)
    assert.equal(fetched, false)
})
