const assert = require("node:assert/strict")
const test = require("node:test")
const loadTs = require("./load-ts.cjs")

function setup(t, overrides = {}, fetchOverride) {
    const oldFetch = global.fetch
    const oldDev = global.__DEV__
    global.__DEV__ = false
    t.after(() => { global.fetch = oldFetch; global.__DEV__ = oldDev })
    const values = new Map()
    let challenge = 0, generated = 0, active = 0, peak = 0
    global.fetch = fetchOverride ?? (async (url, init) => new Response(JSON.stringify(url.endsWith("/challenge")
        ? { challenge: `challenge-${++challenge}` }
        : url.endsWith("/verify") ? { grant: JSON.parse(init.body).assertion }
        : { key_id: "key-1", environment: "production" }), { status: 200 }))
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

test("development builds still obtain real device proof", async t => {
    const api = setup(t)
    global.__DEV__ = true
    const headers = await api.getAppIntegrityHeaders("ai-companion")
    assert.equal(headers["X-App-Integrity-Key-Id"], "key-1")
    assert.match(headers["X-App-Integrity-Token"], /^ios-grant:assertion-/)
    assert.equal(api.stats().generated, 1)
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
    assert.equal(headers["X-App-Integrity-Token"], "ios-grant:assertion")
    assert.equal(api.stats().generated, 1)
})

test("a hung native call has a deadline and releases the iOS request queue", async t => {
    const originalTimeout = global.setTimeout
    global.setTimeout = (callback, delay, ...args) => originalTimeout(callback, delay === 20000 ? 30 : delay, ...args)
    t.after(() => { global.setTimeout = originalTimeout })
    let calls = 0
    let finishLate
    const api = setup(t, { generateAssertionAsync: async () => {
        if (++calls === 1) return new Promise(resolve => { finishLate = resolve })
        return "second-assertion"
    } })
    await assert.rejects(api.getAppIntegrityHeaders("orders:create"), /integrity_timeout/)
    const headers = await api.getAppIntegrityHeaders("orders:create")
    assert.equal(headers["X-App-Integrity-Token"], "ios-grant:second-assertion")
    finishLate("expired-assertion")
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

test("server acknowledges counters in order while a community request overtakes a slow upload", async t => {
    let counter = 0, acknowledged = 0, challenge = 0, releaseUpload, uploadStarted
    const started = new Promise(resolve => { uploadStarted = resolve })
    const upload = new Promise(resolve => { releaseUpload = resolve })
    const grants = new Set()
    const integrity = setup(t, {
        generateAssertionAsync: async () => {
            assert.equal(acknowledged, counter, "previous proof must reach the server first")
            return String(++counter)
        },
    }, async (url, init) => {
        if (url.endsWith("/challenge")) return Response.json({ challenge: `nonce-${++challenge}` })
        if (url.endsWith("/register")) return Response.json({ key_id: "key-1", environment: "production" })
        if (url.endsWith("/verify")) {
            const payload = JSON.parse(init.body)
            await new Promise(resolve => setTimeout(resolve, 10))
            assert.equal(Number(payload.assertion), acknowledged + 1)
            acknowledged = Number(payload.assertion)
            const grant = `permit-${acknowledged}`
            grants.add(`ios-grant:${grant}`)
            return Response.json({ grant })
        }
        const token = init.headers.get("X-App-Integrity-Token")
        assert.ok(grants.delete(token), "a request needs its own verified single-use permit")
        if (url.endsWith("/upload")) { uploadStarted(); await upload }
        return Response.json({ ok: true })
    })
    const api = loadTs("services/api/client.ts", {
        "@/services/api/constants": { API_BASE_URL: "https://example.test" },
        "@/services/app-integrity": integrity,
        "@/services/auth/session": { getAuthTokens: () => ({ accessToken: "test", sessionId: 1 }) },
        "react-native": { Platform: { OS: "ios" } },
        "@/screens/chat/companion-timezones": { deviceCompanionTimezone: () => "UTC" },
        "@/services/api/request-deadline": loadTs("services/api/request-deadline.ts"),
    })
    const slow = api.apiPostMultipart("/upload", new FormData(), { appIntegrityAction: "ai-companion" })
    try {
        await started
        assert.deepEqual(await api.apiGet("/community", undefined, { appIntegrityAction: "community:read" }), { ok: true })
        assert.equal(acknowledged, 2)
    } finally { releaseUpload() }
    assert.deepEqual(await slow, { ok: true })
})

test("a rejected preverification never produces request headers", async t => {
    let challenge = 0
    const api = setup(t, {}, async url => {
        if (url.endsWith("/challenge")) return Response.json({ challenge: `nonce-${++challenge}` })
        if (url.endsWith("/verify")) return Response.json({ detail: "App integrity check failed" }, { status: 403 })
        return Response.json({ key_id: "key-1", environment: "production" })
    })
    await assert.rejects(api.getAppIntegrityHeaders("ai-companion"), api.AppIntegrityUnavailableError)
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

test("device verification is required for every session and platform", async () => {
    for (const [platform, auth] of [
        ["ios", true],
        ["ios", false],
        ["android", true],
    ]) {
        let askedForProof = false
        let headers
        const api = loadTs("services/api/client.ts", {
            "@/services/api/constants": { API_BASE_URL: "https://example.test" },
            "@/services/app-integrity": { getAppIntegrityHeaders: async () => {
                askedForProof = true
                return { "X-App-Integrity-Token": "proof" }
            } },
            "@/services/auth/session": {
                getAuthTokens: () => ({ accessToken: "access" }),
            },
            "react-native": { Platform: { OS: platform } },
            "@/services/api/request-deadline": { fetchTextWithDeadline: async (_url, options) => {
                headers = options.headers
                return { response: new Response(null, { status: 200 }), text: "{}" }
            } },
            "@/screens/chat/companion-timezones": { deviceCompanionTimezone: () => "UTC" },
        })
        await api.apiGet("/mentor", undefined, { auth, appIntegrityAction: "ai-companion" })
        assert.equal(askedForProof, true)
        assert.equal(headers.get("Authorization"), auth ? "Bearer access" : null)
        assert.equal(headers.get("X-App-Platform"), platform)
    }
})
